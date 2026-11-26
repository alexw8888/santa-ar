"""The procedural Santa character shared by every edition.

build_santa_base.py calls `begin`, `character_materials`, `new_mesh`, `character` and `objects` to
make santa_base.blend: the body, face, beard, clothes and two cupped gloves, with no props.
build_santa01.py reuses the materials and the bmesh helpers below to model its kettle and glass.

Geometry is built in one bmesh (`bm`) whose deform layer holds the skin weights, keyed by the bone
indices in GROUPS. Colours are linear; texture maps are converted to sRGB when written.
"""
import bpy, bmesh, math, os, random
import numpy as np
from santa_portrait_fit import fit as fit_portrait, fit_part
import zlib, struct
from mathutils import Vector, Matrix, Quaternion, Euler

HERE = os.path.dirname(os.path.abspath(__file__))
# One seeded generator, drawn in a fixed order, so every build makes the same beard and fur.
rng = random.Random(125)
TAU = math.tau
texture_dir = os.path.join(HERE, 'generated', 'santa')


def begin(version):
    """Empty scene at 24 fps; generated textures are written under generated/<version>."""
    global texture_dir
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = 24
    texture_dir = os.path.join(HERE, 'generated', version)
    os.makedirs(texture_dir, exist_ok=True)
    return scene

# -------------------- reproducible, image-based PBR materials (exportable to AR)
def to_srgb(linear):
    linear = np.clip(linear, 0, 1)
    return np.where(linear <= .0031308, linear * 12.92, 1.055 * linear ** (1 / 2.4) - .055)

def image_file(name, data, color_space='sRGB'):
    height, width = data.shape[:2]
    pixels = np.clip(np.rint(data * 255), 0, 255).astype(np.uint8)
    raw = b''.join(b'\x00' + row.tobytes() for row in pixels)
    def chunk(kind, value):
        return struct.pack('>I', len(value)) + kind + value + struct.pack('>I', zlib.crc32(kind + value) & 0xffffffff)
    path = os.path.join(texture_dir, name + '.png')
    with open(path, 'wb') as output:
        output.write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)) +
                     chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))
    im = bpy.data.images.load(path, check_existing=False)
    im.name = name
    im.colorspace_settings.name = color_space
    im.pack()
    return im

def noise(size, sx, sy=None, seed=0):
    """Tileable band-limited noise; sx/sy are feature sizes in pixels (anisotropic when they differ)."""
    sy = sx if sy is None else sy
    white = np.random.default_rng(seed).normal(size=(size, size))
    fy = np.fft.fftfreq(size)[:, None] * TAU
    fx = np.fft.fftfreq(size)[None, :] * TAU
    result = np.real(np.fft.ifft2(np.fft.fft2(white) * np.exp(-((fx * sx) ** 2 + (fy * sy) ** 2))))
    return result / result.std()

def unit(values):
    return 1 / (1 + np.exp(-values))

def normal_map(height, strength):
    dy, dx = np.gradient(height)
    normal = np.stack((-dx * strength, -dy * strength, np.ones_like(dx)), axis=-1)
    return normal / np.linalg.norm(normal, axis=-1)[:, :, None] * .5 + .5

def velvet_maps(name, size=1024):
    """Bake portable fiber normals and roughness from the generated velvet swatch."""
    source = bpy.data.images.load(os.path.join(HERE, 'assets', 'textures', 'santa01-velvet-source.png'), check_existing=False)
    source.colorspace_settings.name = 'Non-Color'
    source.scale(size, size)
    pixels = np.empty(size * size * 4, dtype=np.float32)
    source.pixels.foreach_get(pixels)
    rgb = pixels.reshape(size, size, 4)[::-1, :, :3].copy()
    bpy.data.images.remove(source)
    luminance = rgb[:, :, 0] * .65 + rgb[:, :, 1] * .25 + rgb[:, :, 2] * .10
    low, high = np.percentile(luminance, (3, 97))
    nap = np.clip((luminance - low) / max(high - low, .01), 0, 1)
    roughness = np.clip(.94 - .19 * nap, .72, .96)
    orm = np.stack((.96 + .04 * nap, roughness, np.zeros_like(nap)), axis=-1)
    return (image_file(name + '_color', rgb),
            image_file(name + '_normal', normal_map(nap * .12, 20), 'Non-Color'),
            image_file(name + '_orm', orm, 'Non-Color'))

def pbr_maps(name, color, kind, size=512):
    """Color (converted from linear to sRGB), tangent normal and occlusion/roughness/metal maps."""
    if kind == 'cloth':
        return velvet_maps(name)
    seed = sum(map(ord, name))
    base = np.array(color)[None, None, :]
    metallic = 0
    if kind == 'plush':
        # Soft clumps with darker crevices and fine fibers: reads as plush fur at AR distances.
        clumps = noise(size, 9, seed=seed)
        tufts = noise(size, 3, seed=seed + 1)
        fibers = noise(size, .6, 6, seed=seed + 2)
        height = .65 * np.tanh(clumps) + .25 * tufts + .18 * fibers
        shade = unit(1.6 * height)
        rgb = base * (.70 + .34 * shade[:, :, None])
        rgb[:, :, 2] *= .97 + .03 * shade
        rough = .93 - .05 * shade
        occlusion = .80 + .20 * shade
        strength = 4.5
    elif kind == 'hair':
        # Fine strands that run along each lock (texture v), grouped into soft bundles.
        strands = noise(size, 1.2, 39, seed=seed)
        bundles = noise(size, 6, 50, seed=seed + 1)
        finer = noise(size, .76, 70, seed=seed + 2)
        height = .42 * strands + .36 * bundles + .32 * finer
        shade = unit(1.5 * height)
        rgb = base * (.63 + .40 * shade[:, :, None])
        rough = .64 - .12 * shade
        occlusion = .82 + .18 * shade
        strength = 3.0
    elif kind in ('leather', 'boot', 'belt'):
        grain = noise(size, 1.6, seed=seed)
        creases = -np.abs(noise(size, 4, 1.5, seed=seed + 1))
        height = .35 * grain + .65 * creases
        rgb = base * (.90 + .12 * unit(2 * grain)[:, :, None] + .10 * creases[:, :, None] / 3)
        rough = .52 + .06 * grain / 3 - .05 * creases
        if kind == 'boot':
            # Worn, lighter scuffs on a mid-brown working boot.
            scuff = unit(2.2 * noise(size, 24, seed=seed + 3) - .8)
            light = np.array((.25, .11, .05))[None, None, :]
            rgb = rgb * (1 - .55 * scuff[:, :, None]) + light * .55 * scuff[:, :, None]
            rough = rough + .14 * scuff
        occlusion = np.clip(1 + .25 * creases / 3, .7, 1)
        strength = 2.5
    else:  # brass
        scratches = noise(size, .45, 60, seed=seed)
        patina = noise(size, 20, seed=seed + 1)
        height = .5 * scratches
        rgb = base * (.92 + .10 * unit(patina)[:, :, None] - .04 * np.abs(scratches)[:, :, None] / 3)
        rough = .24 + .06 * unit(patina) + .03 * np.abs(scratches) / 3
        occlusion = np.ones_like(height)
        metallic = 1
        strength = .6
    orm = np.stack((occlusion, np.clip(rough, .05, 1), np.full_like(height, metallic)), axis=-1)
    return (image_file(name + '_color', to_srgb(rgb)),
            image_file(name + '_normal', normal_map(height, strength), 'Non-Color'),
            image_file(name + '_orm', orm, 'Non-Color'))

MATS = []
def material(name, color, rough=.5, metal=0, texture=None, alpha=1, sheen=0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, alpha)
    mat.use_nodes = True
    bs = mat.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (*color, alpha)
    bs.inputs['Roughness'].default_value = rough
    bs.inputs['Metallic'].default_value = metal
    bs.inputs['Alpha'].default_value = alpha
    if alpha < 1:
        mat.surface_render_method = 'DITHERED'
        mat.use_transparency_overlap = False
    if texture:
        color_im, normal_im, orm_im = pbr_maps(name, color, texture, 512)
        nt = mat.node_tree
        def tex(im):
            node = nt.nodes.new('ShaderNodeTexImage'); node.image = im
            return node.outputs['Color']
        nt.links.new(tex(color_im), bs.inputs['Base Color'])
        normal = nt.nodes.new('ShaderNodeNormalMap')
        normal.inputs['Strength'].default_value = {'cloth': .9, 'plush': .8, 'hair': .58}.get(texture, .5)
        nt.links.new(tex(normal_im), normal.inputs['Color'])
        nt.links.new(normal.outputs['Normal'], bs.inputs['Normal'])
        separate = nt.nodes.new('ShaderNodeSeparateColor')
        nt.links.new(tex(orm_im), separate.inputs['Color'])
        nt.links.new(separate.outputs['Green'], bs.inputs['Roughness'])
        nt.links.new(separate.outputs['Blue'], bs.inputs['Metallic'])
        if texture == 'cloth':
            bs.inputs['Specular IOR Level'].default_value = .25
            sheen = sheen or .38
            bs.inputs['Sheen Tint'].default_value = (.65, .13, .15, 1)
    if sheen:
        # Optional glTF sheen; core color/normal/roughness maps still work without it.
        bs.inputs['Sheen Weight'].default_value = sheen
        bs.inputs['Sheen Roughness'].default_value = .8
        if texture != 'cloth':
            bs.inputs['Sheen Tint'].default_value = (1, 1, 1, 1)
    MATS.append(mat)
    return mat.name


# Material names. `character_materials` creates them in a new scene; `reuse_materials` rebinds them
# (and the helpers' material slots) to the ones already in an opened santa_base.blend.
CHARACTER_MATERIALS = [
    ('RED', 'Crimson_velvet', (.44, .012, .023), dict(texture='cloth')),
    ('FUR', 'Ivory_plush_fur', (.80, .77, .70), dict(texture='plush', sheen=.5)),
    ('HAIR', 'Silver_beard', (.86, .80, .72), dict(texture='hair', sheen=.34)),
    ('SKIN', 'Warm_skin', (.54, .245, .148), dict(rough=.54)),
    ('ROSY', 'Rosy_nose', (.78, .25, .20), dict(rough=.45)),
    ('LEATHER', 'Brown_glove_leather', (.075, .030, .015), dict(texture='leather')),
    ('BOOT', 'Worn_boot_leather', (.11, .042, .017), dict(texture='boot')),
    ('BELT', 'Dark_belt_leather', (.022, .016, .012), dict(texture='belt')),
    ('SOLE', 'Dark_soles', (.016, .010, .007), dict(rough=.7)),
    ('BRASS', 'Golden_brass', (.74, .50, .17), dict(texture='brass')),
    ('GOLD', 'Polished_brass_edges', (.82, .60, .24), dict(rough=.2, metal=1)),
    ('WHITE', 'Soft_eye_whites', (.279, .224, .179), dict(rough=.43)),
    ('IRIS', 'Hazel_eyes', (.053, .025, .010), dict(rough=.31)),
    ('BLACK', 'Pupils', (.006, .003, .002), dict(rough=.2)),
    ('LAUGH', 'Laughing_mouth', (.022, .004, .003), dict(rough=.62)),
    ('NOSTRIL', 'Nose_recess', (.11, .022, .012), dict(rough=.56)),
    ('TEETH', 'Teeth', (.70, .618, .467), dict(rough=.39)),
    ('TONGUE', 'Tongue', (.25, .043, .035), dict(rough=.56)),
    ('LIP', 'Warm_lips', (.55, .17, .13), dict(rough=.43)),
    ('STITCH', 'Leather_stitching', (.25, .14, .065), dict(rough=.75)),
    ('FACE', 'Laughing_face_skin', (.80, .42, .30), dict(rough=.55)),
    ('WIRE', 'Spectacle_gold', (.57, .33, .095), dict(rough=.24, metal=1)),
    ('HAT', 'Scarlet_hat_velvet', (.44, .012, .023), {}),
]
for _key, _name, *_ in CHARACTER_MATERIALS:
    globals()[_key] = _name
# Physical texture repeat, in meters, for materials whose look depends on scale.
TILE = {RED: .36, HAT: .36, FUR: .16, BOOT: .30, BELT: .30, LEATHER: .20}


def expression_creases(x, z, exp):
    """Evaluate the same expression lines for the face mesh and skin maps."""
    eye_x = abs(x) - .068
    fold_z = 1.764 + 4.2 * eye_x ** 2 + .12 * eye_x
    under_eye = exp(-(eye_x / .049) ** 4) * exp(-((z - fold_z) / .00245) ** 2)
    under_eye += .69 * exp(-((eye_x - .006) / .045) ** 4
                           - ((z - fold_z + .008 + .054 * eye_x) / .0019) ** 2)
    under_eye += .35 * exp(-((eye_x - .011) / .039) ** 4
                           - ((z - fold_z + .015 - .047 * eye_x) / .0017) ** 2)
    temple_x = abs(x) - .104
    crow = sum(weight * exp(-((temple_x - distance) / .020) ** 2
                            - ((z - 1.776 - slope * temple_x) / .00165) ** 2)
               for weight, distance, slope in ((1, .014, -.51), (.64, .020, -.19), (.46, .019, .15)))
    forehead = exp(-(x / .082) ** 4) * (
        exp(-((z - 1.858 - 2.1 * x ** 2) / .00185) ** 2)
        + .53 * exp(-((z - 1.870 - 2.9 * x ** 2) / .00160) ** 2))
    brow_furrow = exp(-((z - 1.829) / .018) ** 2) * (
        exp(-((x - .010 - .21 * (z - 1.829)) / .00185) ** 2)
        + .63 * exp(-((x + .012 + .16 * (z - 1.826)) / .00170) ** 2))
    forehead += .66 * brow_furrow
    return under_eye, crow, forehead


def character_materials():
    """Create Santa's materials and generated textures, including the rosy-cheeked face map."""
    for key, name, color, options in CHARACTER_MATERIALS:
        if name == HAT:
            velvet = bpy.data.materials[RED].copy()
            velvet.name = name
            shader = velvet.node_tree.nodes['Principled BSDF']
            shader.inputs['Specular IOR Level'].default_value = .09
            shader.inputs['Sheen Weight'].default_value = .25
            shader.inputs['Sheen Tint'].default_value = (.18, .005, .008, 1)
            MATS.append(velvet)
        else:
            assert material(name, color, **options) == name
    size = 768
    y, x = np.mgrid[0:size, 0:size].astype(float) / (size - 1)
    source = bpy.data.images.load(os.path.join(HERE, 'assets', 'textures', 'santa-portrait-skin-detail.png'))
    source.colorspace_settings.name = 'Non-Color'
    sample_width, sample_height = source.size
    pixels = np.empty(sample_width * sample_height * 4, dtype=np.float32)
    source.pixels.foreach_get(pixels)
    sample = pixels.reshape(sample_height, sample_width, 4)[::-1, :, 0]
    detail = sample[(y * size).astype(int) % sample_height, (x * size).astype(int) % sample_width] - .5
    bpy.data.images.remove(source)
    face_x = (x - .5) * .40
    face_z = (.5 - y) * .43 + 1.727
    cheek = np.exp(-((abs(face_x) - .113) / .062) ** 2 - ((face_z - 1.721) / .039) ** 2)
    nose = np.exp(-(face_x / .053) ** 2 - ((face_z - 1.714) / .031) ** 2)
    eye = np.exp(-((abs(face_x) - .068) / .047) ** 2 - ((face_z - 1.775) / .018) ** 2)
    freckles = unit(2.5 * noise(size, 2, seed=30) - 4.6)
    blush = np.clip(.84 * cheek + .90 * nose + .19 * eye, 0, 1)
    nostrils = np.exp(-((abs(face_x) - .043) / .014) ** 2
                      - ((face_z - 1.693 - .14 * (abs(face_x) - .043)) / .0039) ** 2)
    smile_folds, crow_feet, forehead = expression_creases(face_x, face_z, np.exp)
    skin_linear = np.array((.55, .258, .153))
    rosy_linear = np.array((.52, .126, .079))
    face_linear = (skin_linear + (rosy_linear - skin_linear) * blush[:, :, None])
    color_variation = .033 * np.tanh(noise(size, 15, seed=90)) + .025 * np.tanh(noise(size, 3, seed=75))
    face_linear *= (1 + color_variation - .20 * freckles * blush + .13 * detail)[:, :, None]
    # Transfer color and small-scale relief from selected skin regions of the reference.
    portrait = bpy.data.images.load(os.path.join(HERE, 'assets', 'textures', 'santa-portrait-skin-regions.png'))
    portrait.colorspace_settings.name = 'Non-Color'
    if tuple(portrait.size) != (size, size):
        portrait.scale(size, size)
    portrait_pixels = np.empty(size * size * 4, dtype=np.float32)
    portrait.pixels.foreach_get(portrait_pixels)
    rgba = portrait_pixels.reshape(size, size, 4)[::-1]
    rgb, coverage = rgba[:, :, :3], rgba[:, :, 3]
    reference_linear = np.where(rgb <= .04045, rgb / 12.92, ((rgb + .055) / 1.055) ** 2.4)
    blend = .56 * coverage[:, :, None]
    face_linear = face_linear * (1 - blend) + reference_linear * blend
    face_linear *= (1 - .42 * nostrils - .123 * smile_folds - .091 * crow_feet - .057 * forehead)[:, :, None]
    face_linear *= np.array((.91, .83, .79))
    luma = rgb @ np.array((.26, .58, .16), dtype=np.float32)
    low = sum(np.roll(luma, (dy, dx), axis=(0, 1)) for dy in (-3, 0, 3) for dx in (-3, 0, 3)) / 9
    sample_relief = np.clip((luma - low) * 9, -.28, .28) * coverage ** 1.8
    bpy.data.images.remove(portrait)
    face_image = image_file('Santa_rosy_cheeks', to_srgb(face_linear))
    pores = np.minimum(0, noise(size, .8, seed=32) + .26)
    microfolds = .24 * noise(size, 2.5, .55, seed=59)
    face_height = (.62 * pores + microfolds + 1.36 * detail + sample_relief
                   - .36 * smile_folds - .27 * crow_feet - .18 * forehead)
    face_normal = image_file('Santa_skin_normal', normal_map(face_height, .44), 'Non-Color')
    face_material = bpy.data.materials[FACE]
    nodes, links = face_material.node_tree.nodes, face_material.node_tree.links
    skin = nodes['Principled BSDF']
    skin.inputs['Subsurface Weight'].default_value = .095
    skin.inputs['Subsurface Scale'].default_value = .006
    skin.inputs['Specular IOR Level'].default_value = .28
    face_tex = nodes.new('ShaderNodeTexImage')
    face_tex.image = face_image
    links.new(face_tex.outputs['Color'], skin.inputs['Base Color'])
    pores_tex = nodes.new('ShaderNodeTexImage')
    pores_tex.image = face_normal
    normals = nodes.new('ShaderNodeNormalMap')
    normals.inputs['Strength'].default_value = .67
    links.new(pores_tex.outputs['Color'], normals.inputs['Color'])
    links.new(normals.outputs['Normal'], skin.inputs['Normal'])

    # The curved eye patch uses angular U and radial V, so individual rays follow the iris.
    y, x = np.mgrid[0:256, 0:512].astype(float)
    radial, angle = y / 255, x / 512 * TAU
    rays = (.30 * np.cos(39 * angle + 2.9 * radial)
            + .18 * np.cos(83 * angle - 3.7 * radial)
            + .15 * np.cos(137 * angle + 5.1 * radial))
    iris = np.array((.039, .019, .008)) * (1 + rays[:, :, None])
    pupil = np.clip((radial - .62) / .043, 0, 1)
    edge = np.clip((radial - .89) / .108, 0, 1)
    dark = edge * .85 + (1 - pupil) * .96
    iris = iris * (1 - dark[:, :, None]) + np.array((.004, .0027, .0018)) * dark[:, :, None]
    eye_image = image_file('Santa_iris', to_srgb(iris))
    eye = bpy.data.materials[IRIS].node_tree
    eye_texture = eye.nodes.new('ShaderNodeTexImage')
    eye_texture.image = eye_image
    iris_shader = eye.nodes['Principled BSDF']
    iris_shader.inputs['Specular IOR Level'].default_value = .29
    eye.links.new(eye_texture.outputs['Color'], iris_shader.inputs['Base Color'])

    # The lip blends into the cheek, with fine creases along the curve of the smile.
    blend = np.linspace(1, 0, 256)[:, None, None]
    lip = np.array((.54, .117, .073)) * (1 - blend) + np.array((.55, .193, .099)) * blend
    striae = .35 * noise(256, .55, 6, seed=583) + .14 * noise(256, 2.1, 5, seed=709)
    striae *= np.sin(np.pi * blend[:, :, 0]) ** .7
    lip_image = image_file('Santa_lip_color', to_srgb(lip * (1 + .13 * striae[:, :, None])))
    lip_normal = image_file('Santa_lip_normal', normal_map(striae, .73), 'Non-Color')
    lips = bpy.data.materials[LIP].node_tree
    lip_texture = lips.nodes.new('ShaderNodeTexImage')
    lip_texture.image = lip_image
    lips.links.new(lip_texture.outputs['Color'], lips.nodes['Principled BSDF'].inputs['Base Color'])
    grooves = lips.nodes.new('ShaderNodeTexImage')
    grooves.image = lip_normal
    lip_bump = lips.nodes.new('ShaderNodeNormalMap')
    lip_bump.inputs['Strength'].default_value = .32
    lips.links.new(grooves.outputs['Color'], lip_bump.inputs['Color'])
    lips.links.new(lip_bump.outputs['Normal'], lips.nodes['Principled BSDF'].inputs['Normal'])


def reuse_materials():
    """Point the helpers at the materials of an opened santa_base.blend (for adding props)."""
    MATS.clear()
    for key, name, *_ in CHARACTER_MATERIALS:
        if name in bpy.data.materials:
            MATS.append(bpy.data.materials[name])


# -------------------- skeleton and prop anchors
CUP = Vector((.15, -.48, 1.12))
KETTLE = Vector((-.44, -.40, 1.53))
SHOULDERS = {'L': Vector((.265, 0, 1.43)), 'R': Vector((-.265, 0, 1.43))}
UPPER, LOWER = .31, .30
SHOULDER_BALL = .13  # radius of the round shoulder at each arm joint (the sleeve top fits inside)

def elbow_for(side, wrist):
    shoulder = SHOULDERS[side]
    direction = wrist - shoulder
    d = min(direction.length, UPPER + LOWER - .001)
    unit_dir = direction.normalized()
    a = (UPPER * UPPER - LOWER * LOWER + d * d) / (2 * d)
    guide = Vector((1 if side == 'L' else -1, .08, -.5))
    perp = (guide - unit_dir * guide.dot(unit_dir)).normalized()
    return shoulder + unit_dir * a + perp * math.sqrt(max(0, UPPER * UPPER - a * a))

WRISTS = {'L': CUP + Vector((.16, .04, 0)), 'R': KETTLE + Vector((0, .08, .02))}
GRIPS = {'L': CUP + Vector((.10, 0, 0)), 'R': KETTLE + Vector((0, -.005, .015))}
BONES = [
 ('root', (0, 0, 0), (0, .15, 0), None),
 ('hips', (0, 0, .86), (0, 0, 1.05), 'root'),
 ('spine', (0, 0, 1.05), (0, 0, 1.29), 'hips'),
 ('chest', (0, 0, 1.29), (0, 0, 1.53), 'spine'),
 ('neck', (0, 0, 1.53), (0, 0, 1.60), 'chest'),
 ('head', (0, 0, 1.60), (0, 0, 1.86), 'neck'),
]
for side, sign in (('L', 1), ('R', -1)):
    shoulder, elbow, wrist = SHOULDERS[side], elbow_for(side, WRISTS[side]), WRISTS[side]
    BONES += [(f'upper_arm.{side}', shoulder, elbow, 'chest'),
              (f'forearm.{side}', elbow, wrist, f'upper_arm.{side}'),
              (f'hand.{side}', wrist, GRIPS[side], f'forearm.{side}'),
              (f'thigh.{side}', (sign * .16, 0, .86), (sign * .205, 0, .46), 'hips'),
              (f'shin.{side}', (sign * .205, 0, .46), (sign * .225, 0, .12), f'thigh.{side}'),
              (f'foot.{side}', (sign * .225, 0, .12),
               (sign * (.225 + .17 * math.sin(math.radians(14))), -.17 * math.cos(math.radians(14)), .06), f'shin.{side}')]
# Eye bones pivot a little behind each iris in the widened head and point forward.
HEAD_SCALE = Vector((1.22, 1.06, 1))
HEAD_HEIGHTS = np.array([
    (1.30, 1.30), (1.32, 1.32), (1.47, 1.446), (1.535, 1.505), (1.58, 1.539),
    (1.62, 1.576), (1.66, 1.622), (1.70, 1.680), (1.73, 1.721),
    (1.77, 1.755), (1.80, 1.786), (1.855, 1.850), (1.89, 1.894),
    (1.92, 1.928), (2.03, 2.030), (2.20, 2.20),
])


def head_height(z):
    """Map sculpt heights to the reference proportions while keeping the chin and crown in place."""
    return np.interp(z, HEAD_HEIGHTS[:, 0], HEAD_HEIGHTS[:, 1])


EYE_CENTER = (.067, -.102, 1.774)
EYE_PIVOTS = {side: Vector(fit_portrait(np.array((sign * EYE_CENTER[0], EYE_CENTER[1], head_height(EYE_CENTER[2]))) * np.array(HEAD_SCALE)))
              for side, sign in (('L', 1), ('R', -1))}
for side, pivot in EYE_PIVOTS.items():
    BONES.append((f'eye.{side}', pivot, pivot + Vector((0, -.04, 0)), 'head'))
SEG ={name: (Vector(h), Vector(t)) for name, h, t, parent in BONES}
GROUPS = {name: i for i, (name, *_) in enumerate(BONES)}


def add_bone(name, head, tail, parent):
    """Register an extra (prop) bone so the helpers can bind vertices to it."""
    BONES.append((name, Vector(head), Vector(tail), parent))
    SEG[name] = (Vector(head), Vector(tail))
    GROUPS[name] = len(GROUPS)


bm = DL = UV = None


def new_mesh():
    """Start a new bmesh for the helpers below to build into."""
    global bm, DL, UV
    bm = bmesh.new()
    DL = bm.verts.layers.deform.verify()
    UV = bm.loops.layers.uv.verify()
    return bm


# -------------------- geometry helpers with portable UVs and skin weights
def weights(p, names):
    if isinstance(names, str): return {names: 1}
    values = {}
    for name in names:
        a, b = SEG[name]; ab = b - a
        t = max(0, min(1, (p - a).dot(ab) / ab.length_squared))
        values[name] = 1 / ((p - a - t * ab).length ** 4 + 1e-8)
    total = sum(values.values())
    values = {k: v / total for k, v in values.items() if v / total > .015}
    total = sum(values.values())
    return {k: v / total for k, v in values.items()}

def finish(vertices, mat, bones):
    index = next(i for i, m in enumerate(MATS) if m.name == mat)
    faces = set()
    for vertex in vertices:
        faces.update(vertex.link_faces)
        for name, w in weights(vertex.co, bones).items(): vertex[DL][GROUPS[name]] = w
    for face in faces:
        face.material_index = index; face.smooth = True

def waves(count, along, around_max):
    """Random interfering waves; `along` is a frequency (per radian or per meter)."""
    return [(along * rng.uniform(.6, 1.4), rng.choice([k for k in range(-around_max, around_max + 1) if k]),
             rng.uniform(0, TAU)) for _ in range(count)]

def wave_value(ws, s, a):
    return sum(math.sin(f * s + k * a + p) for f, k, p in ws) / math.sqrt(len(ws) / 2)

def face_uv(co):
    return (co.x / .40 + .5, (co.z - 1.727) / .43 + .5)


def ellipsoid(c, r, mat, bones='head', seg=24, rings=14, direction=None, euler=None, lumpy=0, warp=None):
    rot = Matrix.Identity(3)
    if direction is not None: rot = Vector(direction).to_track_quat('Z', 'Y').to_matrix()
    if euler is not None:
        rot = Euler(tuple(math.radians(v) for v in euler)).to_matrix()
    c = Vector(c)
    transform = Matrix.Translation(c) @ rot.to_4x4() @ Matrix.Diagonal((*r, 1))
    verts = bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1, matrix=transform, calc_uvs=True)['verts']
    if lumpy:
        # Rounded clumps in every direction (a pompom), rather than random spikes.
        size = sum(r) / 3
        dirs = [(Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1))).normalized() * TAU / (size * .55),
                 rng.uniform(0, TAU)) for _ in range(10)]
        for v in verts:
            offset = v.co - c
            value = sum(math.sin(k.dot(offset) + p) for k, p in dirs) / math.sqrt(5)
            v.co += offset.normalized() * size * lumpy * value
    if warp:
        for v in verts:
            v.co = warp(v.co)
    faces = {face for v in verts for face in v.link_faces}
    if mat == FACE:
        for face in faces:
            for loop in face.loops:
                co = loop.vert.co
                loop[UV].uv = face_uv(co)
    elif mat in TILE:
        around = TAU * (r[0] + r[1]) / 2 / TILE[mat]
        for face in faces:
            for loop in face.loops:
                loop[UV].uv = (loop[UV].uv.x * around, loop[UV].uv.y * around / 2)
    finish(verts, mat, bones)

def uv_face(verts, coords):
    f = bm.faces.new(verts)
    for loop, uv in zip(f.loops, coords): loop[UV].uv = uv
    return f

def tube(points, radii, mat, bones='head', sides=10, sub=2, cap=True, cloth_folds=0, flat=1, lumpy=0):
    """Swept tube. `flat` squashes the cross-section in its depth direction (hair ribbons);
    `lumpy` adds smooth plush clumps along its length."""
    pts = [Vector(p) for p in points]; P = []; R = []
    for i in range(len(pts) - 1):
        for j in range(sub):
            t = j / sub; P.append(pts[i].lerp(pts[i + 1], t)); R.append(radii[i] * (1 - t) + radii[i + 1] * t)
    P.append(pts[-1]); R.append(radii[-1])
    lengths = [0]
    for i in range(1, len(P)): lengths.append(lengths[-1] + (P[i] - P[i - 1]).length)
    ws = waves(7, TAU / .07, 2) if lumpy else None
    rings = []
    n = None
    for i, (p, r) in enumerate(zip(P, R)):
        tangent = (P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]).normalized()
        if n is None:
            n = tangent.cross(Vector((0, 0, 1)) if abs(tangent.z) < .95 else Vector((1, 0, 0))).normalized()
        n = (n - tangent * n.dot(tangent)).normalized(); b = tangent.cross(n)
        ring = []
        for j in range(sides):
            a = TAU * j / sides; rr = r
            if lumpy: rr *= 1 + lumpy * wave_value(ws, lengths[i], a)
            progress = i / max(1, len(P) - 1)
            rr += cloth_folds * math.exp(-((progress - .53) / .24) ** 2) * math.cos(progress * TAU * 5 + 1.3 * math.sin(a * 2))
            ring.append(bm.verts.new(p + (math.cos(a) * n * flat + math.sin(a) * b) * rr))
        rings.append(ring)
    total = max(lengths[-1], 1e-5)
    def tube_uv(i, j):
        if mat in TILE:
            return (j / sides * TAU * R[i] / TILE[mat], lengths[i] / TILE[mat])
        return (j / sides, lengths[i] / total)
    for i, (a, b) in enumerate(zip(rings, rings[1:])):
        for j in range(sides):
            uv_face((a[j], a[(j + 1) % sides], b[(j + 1) % sides], b[j]),
                    (tube_uv(i, j), tube_uv(i, j + 1), tube_uv(i + 1, j + 1), tube_uv(i + 1, j)))
    if cap:
        bm.faces.new(tuple(reversed(rings[0]))); bm.faces.new(tuple(rings[-1]))
    finish([v for ring in rings for v in ring], mat, bones)

def torus(c, normal, major, minor, mat, bones='head', depth=None, sides=48, cross=8, lumpy=0):
    c = Vector(c); rot = Vector(normal).to_track_quat('Z', 'Y').to_matrix()
    ws = waves(9, TAU * major / .075, 2) if lumpy else None
    rings = []
    for i in range(sides):
        a = TAU * i / sides; center = Vector((major * math.cos(a), (depth or major) * math.sin(a), 0))
        radial = Vector((math.cos(a), math.sin(a), 0))
        ring = []
        for j in range(cross):
            v = TAU * j / cross; r = minor
            if lumpy: r *= 1 + lumpy * wave_value(ws, a, v)
            ring.append(bm.verts.new(c + rot @ (center + r * (radial * math.cos(v) + Vector((0, 0, math.sin(v)))))))
        rings.append(ring)
    major_scale = TAU * major / TILE[mat] if mat in TILE else 1
    minor_scale = TAU * minor / TILE[mat] if mat in TILE else 1
    for i in range(sides):
        for j in range(cross):
            uv_face((rings[i][j], rings[(i + 1) % sides][j], rings[(i + 1) % sides][(j + 1) % cross], rings[i][(j + 1) % cross]),
                    ((i / sides * major_scale, j / cross * minor_scale), ((i + 1) / sides * major_scale, j / cross * minor_scale),
                     ((i + 1) / sides * major_scale, (j + 1) / cross * minor_scale), (i / sides * major_scale, (j + 1) / cross * minor_scale)))
    finish([v for ring in rings for v in ring], mat, bones)

def lathe(c, profile, mat, bones, sides=48, ellipse=1, flute=0):
    # profile = (height, radius), optionally with a front/back center offset.
    c = Vector(c); rings = []
    if mat == RED:
        dense = []
        for lower, upper in zip(profile, profile[1:]):
            for step in range(4):
                t = step / 4
                dense.append(tuple(a * (1 - t) + b * t for a, b in zip(lower, upper)))
        profile = dense + [profile[-1]]
    for i, row in enumerate(profile):
        z, r = row[:2]; offset = row[2] if len(row) > 2 else 0
        ring = []
        for j in range(sides):
            a = TAU * j / sides; rr = r + flute * math.cos(16 * a)
            if mat == RED:
                rr += .004 * math.cos(a * 11 + (z - .98) * 13 + math.sin(a * 3)) * math.exp(-((z - 1.035) / .12) ** 2)
                rr += .0025 * math.cos(a * 14) * math.exp(-((z - .78) / .055) ** 2)
            ring.append(bm.verts.new(c + Vector((rr * math.cos(a), rr * ellipse * math.sin(a) + offset, z))))
        rings.append(ring)
    def lathe_uv(i, j):
        if mat in TILE:
            radius = profile[i][1]
            depth = radius * ellipse
            perimeter = math.pi * (3 * (radius + depth) - math.sqrt((3 * radius + depth) * (radius + 3 * depth)))
            return (j / sides * perimeter / TILE[mat], (profile[i][0] - profile[0][0]) / TILE[mat])
        return (j / sides, i / (len(rings) - 1))
    for i in range(len(rings) - 1):
        for j in range(sides):
            uv_face((rings[i][j], rings[i][(j + 1) % sides], rings[i + 1][(j + 1) % sides], rings[i + 1][j]),
                    (lathe_uv(i, j), lathe_uv(i, j + 1), lathe_uv(i + 1, j + 1), lathe_uv(i + 1, j)))
    bm.faces.new(tuple(reversed(rings[0]))); bm.faces.new(tuple(rings[-1]))
    finish([v for ring in rings for v in ring], mat, bones)

def fur_ring(c, normal, major, minor, bones, depth=None, lumpy=.09):
    """Plush trim: a dense torus with soft, interfering clumps (no floating tufts)."""
    sides = max(48, int(TAU * major / .012))
    torus(c, normal, major, minor, FUR, bones, depth=depth, sides=sides, cross=16, lumpy=lumpy)

def character():
    """Model the body, clothes, face, beard, cap, sleeves and the cupped left glove into `bm`."""
    # -------------------- coat, trousers, belt and boots
    BODY = ['hips', 'spine', 'chest']
    # A rounder, portlier coat: a big belly pushed forward over the belt, like the reference photo.
    COAT = [(.69, .31, -.012), (.72, .345, -.014), (.79, .35, -.022), (.91, .39, -.034),
            (1.04, .415, -.048), (1.16, .405, -.040), (1.30, .355, -.012), (1.40, .30, .012), (1.48, .215, .01), (1.53, .11, 0)]
    COAT_DEPTH = .86
    def coat_front(z):
        """Front surface (y) of the coat at height z, and its radius."""
        r = float(np.interp(z, [p[0] for p in COAT], [p[1] for p in COAT]))
        offset = float(np.interp(z, [p[0] for p in COAT], [p[2] for p in COAT]))
        return offset - r * COAT_DEPTH, r, offset
    lathe((0, 0, 0), COAT, RED, BODY, sides=64, ellipse=COAT_DEPTH)
    fur_ring((0, -.014, .72), (0, 0, 1), .352, .070, ['hips'], depth=.305)
    # The fur opening follows the coat front.
    tube([(0, coat_front(z)[0] + .004, z) for z in (.76, .90, 1.06, 1.22, 1.38)] + [(0, -.15, 1.50)],
         [.046, .044, .045, .044, .044, .042], FUR, BODY, sides=16, sub=6, lumpy=.09)
    fur_ring((0, 0, 1.51), (0, 0, 1), .118, .038, ['chest', 'neck'], depth=.096)
    # A wide leather belt band with a large rounded brass buckle, prong and holes.
    belt_rows = []
    for z, extra in ((.930, -.004), (.936, .013), (1.014, .013), (1.020, -.004)):
        _, r, offset = coat_front(z)
        belt_rows.append((z, r + extra, offset))
    lathe((0, 0, 0), belt_rows, BELT, ['hips', 'spine'], sides=64, ellipse=COAT_DEPTH)
    bw, bh, bz = .085, .058, .975
    by = coat_front(bz)[0] - .028
    buckle = [(-bw + .014, by, bz - bh), (bw - .014, by, bz - bh), (bw, by, bz - bh + .014), (bw, by, bz + bh - .014),
              (bw - .014, by, bz + bh), (-bw + .014, by, bz + bh), (-bw, by, bz + bh - .014), (-bw, by, bz - bh + .014),
              (-bw + .014, by, bz - bh)]
    tube(buckle, [.013] * len(buckle), BRASS, ['hips', 'spine'], sides=10, sub=3, flat=.55)
    inner = [(x * .78, by - .004, bz + (z - bz) * .7) for x, _, z in buckle]
    tube(inner, [.0035] * len(inner), GOLD, ['hips', 'spine'], sides=6, sub=3)
    tube([(-bw, by - .008, bz), (.02, by - .010, bz)], [.0055, .004], GOLD, ['hips', 'spine'], sides=8)
    for x in (.13, .165, .20):
        _, r, offset = coat_front(bz)
        hole_y = offset - (r + .013) * COAT_DEPTH * math.sqrt(max(0, 1 - (x / (r + .013)) ** 2)) - .001
        ellipsoid((x, hole_y, bz), (.005, .003, .005), BLACK, ['hips', 'spine'], seg=10, rings=6)
    for sign, side in ((1, 'L'), (-1, 'R')):
        # A wide, sturdy stance: legs splay out from the hips and the boots turn outward.
        hip_x, knee_x, x = sign * .16, sign * .205, sign * .225
        tube([(hip_x, 0, .84), (sign * .182, 0, .67), (knee_x, .012, .47), (x, 0, .30)], [.142, .136, .118, .104], RED,
             ['hips', f'thigh.{side}', f'shin.{side}'], sides=24, sub=4, cloth_folds=.0025)
        fur_ring((x, 0, .31), (0, 0, 1), .118, .058, f'shin.{side}')
        turn = Matrix.Rotation(math.radians(sign * 14), 3, 'Z')
        def at(px, py, pz):
            return Vector((x, 0, 0)) + turn @ Vector((px, py, pz))
        yaw = (0, 0, sign * 14)
        # Mid-brown work boot: shaft, rounded toe, thick dark sole and heel.
        ellipsoid(at(0, .01, .17), (.102, .107, .16), BOOT, f'foot.{side}', seg=28, rings=18, euler=yaw)
        ellipsoid(at(0, -.105, .060), (.124, .210, .056), SOLE, f'foot.{side}', seg=32, rings=14, euler=yaw)
        ellipsoid(at(0, .055, .045), (.104, .085, .042), SOLE, f'foot.{side}', seg=24, rings=10, euler=yaw)
        ellipsoid(at(0, -.105, .104), (.116, .198, .088), BOOT, f'foot.{side}', seg=32, rings=18, euler=yaw)
        ellipsoid(at(0, -.215, .105), (.088, .085, .062), BOOT, f'foot.{side}', seg=24, rings=14, euler=yaw)
        seam = []
        for j in range(20):
            a = math.pi + j * math.pi / 19
            seam.append(at(.110 * math.cos(a), -.10 + .186 * math.sin(a), .072))
        tube(seam, [.0035] * len(seam), STITCH, f'foot.{side}', sides=5, sub=1)
        for j in range(18):
            a = math.pi + j * math.pi / 17
            p = at(.115 * math.cos(a), -.10 + .193 * math.sin(a), .066)
            tube([p, p + Vector((0, 0, .008))], [.0013, .0013], STITCH, f'foot.{side}', sides=4, sub=1)
        # Toe-cap seam, ankle strap and square brass buckle.
        cap_seam = [at(.09 * math.cos(a), -.17 + .07 * math.sin(a) - .06, .135 + .035 * math.sin(a))
                    for a in [math.pi * (1 + k / 14) for k in range(15)]]
        tube(cap_seam, [.003] * len(cap_seam), STITCH, f'foot.{side}', sides=5, sub=1)
        torus(at(0, .006, .215), (0, 0, 1), .106, .014, BELT, f'foot.{side}', depth=.110, sides=40, cross=6)
        p = [at(-.036, -.112, .186), at(.036, -.112, .186), at(.036, -.112, .244), at(-.036, -.112, .244), at(-.036, -.112, .186)]
        tube(p, [.0055] * 5, GOLD, f'foot.{side}', sides=6, sub=2)

    from santa_head import build_head
    build_head()

    # -------------------- arms, tailored sleeves and gripping brown leather gloves
    for side in ('L', 'R'):
        shoulder, elbow, wrist = SHOULDERS[side], elbow_for(side, WRISTS[side]), WRISTS[side]
        upper = f'upper_arm.{side}'; fore = f'forearm.{side}'; hand = f'hand.{side}'
        direction = (wrist - elbow).normalized()
        cuff = wrist - direction * .035
        tube([shoulder + (elbow - shoulder) * -.12, shoulder.lerp(elbow, .28), elbow,
              elbow.lerp(cuff, .55), cuff], [.118, .138, .118, .102, .090], RED, [upper, fore], sides=24, sub=3, cloth_folds=.0035)
        # A round velvet shoulder centred on the joint: turning about its own centre it keeps the same
        # shape at any arm angle, and the top of the sleeve always stays tucked inside it, so the
        # shoulder is never pointed and the sleeve never pokes out of the coat.
        ellipsoid(shoulder, (SHOULDER_BALL,) * 3, RED, upper, seg=32, rings=20)
        fur_ring(cuff, direction, .090, .052, fore)
        for offset in (-.025, .015):
            center = elbow + direction * offset
            torus(center, direction, .113, .006, RED, [upper, fore], sides=24, cross=5)
    # The cupped left glove; `objects` mirrors it onto the right hand.
    hand = 'hand.L'
    ellipsoid(CUP + Vector((.107, .007, -.005)), (.058, .053, .069), LEATHER, hand, seg=24, rings=16)
    for i in range(4):
        z = .049 - i * .029
        s = 1 - .08 * abs(i - 1.5)
        points = [CUP + Vector((.109, -.02, z)), CUP + Vector((.076, -.063 * s, z)),
                  CUP + Vector((.028, -.070 * s, z - .003)), CUP + Vector((.009, -.054 * s, z - .008))]
        tube(points, [.0165, .0175, .0145, .0085], LEATHER, hand, sides=12, sub=3)
        ellipsoid(points[1] + Vector((.004, -.008, 0)), (.008, .006, .011), LEATHER, hand, seg=12, rings=8)
    tube([CUP + Vector((.103, .026, .043)), CUP + Vector((.057, .049, .063)), CUP + Vector((.025, .044, .047))],
         [.022, .020, .012], LEATHER, hand, sides=12, sub=3)


# -------------------- object, rig and skin creation

def mirror_left_glove():
    """Copy the cupped left glove onto the right wrist, mirrored, so both hands can hold a prop."""
    left, right = GROUPS['hand.L'], GROUPS['hand.R']
    glove = [f for f in bm.faces if all(v[DL].get(left, 0) > .999 for v in f.verts)]
    copy = bmesh.ops.duplicate(bm, geom=glove)['geom']
    for v in (item for item in copy if isinstance(item, bmesh.types.BMVert)):
        p = v.co - WRISTS['L']
        v.co = WRISTS['R'] + Vector((-p.x, p.y, p.z))
        del v[DL][left]
        v[DL][right] = 1
    bmesh.ops.reverse_faces(bm, faces=[f for f in copy if isinstance(f, bmesh.types.BMFace)])


def objects(name, scene):
    """Turn `bm` into the skinned character mesh `name` and its armature `name`_Rig."""
    head_groups = [GROUPS[n] for n in ('head', 'eye.L', 'eye.R')]
    vertices = [v for v in bm.verts if sum(v[DL].get(g, 0) for g in head_groups) > .99]
    points = np.array([tuple(v.co) for v in vertices]) * np.array(HEAD_SCALE)
    points[:,2] = head_height(points[:,2])
    fitted = fit_portrait(points)
    part_indices = {}
    for i, vertex in enumerate(vertices):
        if vertex.link_faces:
            part_name = MATS[vertex.link_faces[0].material_index].name
            if part_name in ('Fur brim','Pompom fibers','Folded velvet') or part_name.startswith('Moustache '):
                part_indices.setdefault(part_name,[]).append(i)
    for part_name,indices in part_indices.items():
        fitted[indices] = fit_part(fitted[indices],part_name)
    for vertex, point in zip(vertices, fitted):
        vertex.co = point
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    # Open facial surfaces must face the viewer in AR Quick Look, which culls back faces.
    facial_surfaces = {i for i, material in enumerate(MATS) if material.name in (LAUGH, IRIS, LIP)}
    for face in bm.faces:
        if face.material_index not in facial_surfaces:
            continue
        face.normal_update()
        if face.normal.y > 0:
            face.normal_flip()
    mirror_left_glove()
    mesh = bpy.data.meshes.new(name + '_Mesh'); bm.to_mesh(mesh); bm.free()
    mesh.update(); mesh.calc_loop_triangles()
    character = bpy.data.objects.new(name, mesh); scene.collection.objects.link(character)
    for mat in MATS: mesh.materials.append(mat)
    for group in GROUPS: character.vertex_groups.new(name=group)
    arm = bpy.data.armatures.new(name + '_Rig')
    rig = bpy.data.objects.new(name + '_Rig', arm); scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig; rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    for bone_name, h, t, parent in BONES:
        bone = arm.edit_bones.new(bone_name); bone.head = h; bone.tail = t
        if parent: bone.parent = arm.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    character.parent = rig
    mod = character.modifiers.new('Armature', 'ARMATURE'); mod.object = rig
    for pb in rig.pose.bones: pb.rotation_mode = 'QUATERNION'
    assert all(v.groups and abs(sum(g.weight for g in v.groups) - 1) < 1e-4 for v in mesh.vertices)
    print(f'[model] {len(mesh.vertices):,} vertices, {len(mesh.loop_triangles):,} triangles, {len(MATS)} materials', flush=True)
    return character, rig


def props_object(name, scene, uv_name):
    """Turn `bm` (props modelled with the helpers) into a mesh object ready to join onto Santa."""
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    mesh = bpy.data.meshes.new(name); bm.to_mesh(mesh); bm.free()
    mesh.uv_layers[0].name = uv_name
    ob = bpy.data.objects.new(name, mesh); scene.collection.objects.link(ob)
    for mat in MATS: mesh.materials.append(mat)
    for group in GROUPS: ob.vertex_groups.new(name=group)
    return ob


# -------------------- studio for the editable scene and presentation renders
def studio(scene):
    world = bpy.data.worlds.new('Studio_world'); world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (.28, .32, .40, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = .25
    scene.world = world

    def area(name, position, power, color, size):
        data = bpy.data.lights.new(name, 'AREA'); data.energy = power; data.color = color; data.shape = 'DISK'; data.size = size
        ob = bpy.data.objects.new(name, data); scene.collection.objects.link(ob); ob.location = position
        ob.rotation_euler = (Vector((0, 0, 1.1)) - ob.location).to_track_quat('-Z', 'Y').to_euler()
    area('Key_softbox', (-3, -4, 5), 400, (1, .83, .68), 4)
    area('Fill_softbox', (3, -2, 3), 200, (.75, .86, 1), 3)
    area('Rim_softbox', (1, 3, 4), 500, (1, .78, .56), 3)
    cam = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera')); scene.collection.objects.link(cam)
    cam.location = (2.15, -6.3, 2.75); cam.data.lens = 82
    cam.rotation_euler = (Vector((-.035, -.12, 1.05)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.camera = cam
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, .002))
    floor = bpy.context.object; floor.name = 'Preview_ground'
    floor.is_shadow_catcher = True
    scene.render.engine = 'CYCLES'; scene.cycles.samples = 32; scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 6; scene.cycles.transparent_max_bounces = 6
    scene.render.resolution_x, scene.render.resolution_y = 800, 1000
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'
    scene.view_settings.exposure = -.3
    return cam
