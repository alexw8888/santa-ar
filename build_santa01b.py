"""Build Santa 01b: a closer match to the reference photo of Santa pouring chai.

python3 build_santa01b.py -- [preview_dir] [quick]       (Blender as the `bpy` module)
blender -b --factory-startup --python-exit-code 1 -P build_santa01b.py -- [preview_dir] [quick]

Writes santa01b.blend, packed with its generated PBR textures. `quick` skips the
animation bake and the saved scene and renders only the face and ready previews.

Compared with Santa 01: textures are written in the right color space (gloves and
boots are now brown, the kettle golden brass), the fur trim is plush and lumpy
instead of dotted with spikes, the face grins broadly with an open mouth, the beard,
moustache and eyebrows are fuller, he is portlier with a wide, splayed stance, the
kettle carries raised "Chaiiwala / of London" lettering, and the drink is milky chai.
"""
import bpy, bmesh, math, os, sys, random
import numpy as np
import zlib, struct
from mathutils import Vector, Matrix, Quaternion, Euler

HERE = os.path.dirname(os.path.abspath(__file__))
VERSION = 'santa01b'
NAME = VERSION.capitalize()
ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
QUICK = 'quick' in ARGS
ARGS = [a for a in ARGS if a != 'quick']
PREVIEWS = os.path.abspath(ARGS[0]) if ARGS else None
rng = random.Random(125)
TAU = math.tau
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = 24
scene.frame_start, scene.frame_end = 1, 300

# -------------------- reproducible, image-based PBR materials (exportable to AR)
texture_dir = os.path.join(HERE, 'generated', VERSION)
os.makedirs(texture_dir, exist_ok=True)

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
        strands = noise(size, 1.4, 30, seed=seed)
        bundles = noise(size, 6, 50, seed=seed + 1)
        height = .55 * strands + .55 * bundles
        shade = unit(1.5 * height)
        rgb = base * (.74 + .30 * shade[:, :, None])
        rough = .62 - .10 * shade
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
        normal.inputs['Strength'].default_value = {'cloth': .9, 'plush': .8, 'hair': .7}.get(texture, .5)
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

# Colors are linear; the texture maps are converted to sRGB when written.
RED = material('Crimson_velvet', (.44, .012, .023), texture='cloth')
FUR = material('Ivory_plush_fur', (.80, .77, .70), texture='plush', sheen=.5)
HAIR = material('Silver_beard', (.80, .80, .78), texture='hair', sheen=.3)
SKIN = material('Warm_skin', (.80, .42, .30), .55)
ROSY = material('Rosy_nose', (.78, .25, .20), .45)
LEATHER = material('Brown_glove_leather', (.075, .030, .015), texture='leather')
BOOT = material('Worn_boot_leather', (.11, .042, .017), texture='boot')
BELT = material('Dark_belt_leather', (.022, .016, .012), texture='belt')
SOLE = material('Dark_soles', (.016, .010, .007), .7)
BRASS = material('Golden_brass', (.74, .50, .17), texture='brass')
GOLD = material('Polished_brass_edges', (.82, .60, .24), .2, 1)
ENGRAVE = material('Engraved_lettering', (.075, .040, .014), .45, .4)
WHITE = material('Soft_eye_whites', (.92, .90, .84), .3)
IRIS = material('Hazel_eyes', (.14, .065, .028), .3)
BLACK = material('Pupils', (.006, .003, .002), .2)
MOUTH = material('Mouth_interior', (.085, .010, .007), .8)
LAUGH = material('Laughing_mouth', (.018, .003, .002), .8)
TEETH = material('Teeth', (.80, .76, .66), .35)
TONGUE = material('Tongue', (.55, .12, .10), .5)
LIP = material('Warm_lips', (.55, .17, .13), .5)
CHAI = material('Masala_chai', (.50, .23, .085), .2)
GLASS = material('Clear_glass', (.45, .57, .62), .10, alpha=.14)
STITCH = material('Leather_stitching', (.25, .14, .065), .75)
STEAM = material('Chai_aroma', (.63, .59, .54), .9, alpha=.18)
FACE = material('Laughing_face_skin', (.80, .42, .30), .55)
# Physical texture repeat, in meters, for materials whose look depends on scale.
TILE = {RED: .36, FUR: .16, BOOT: .30, BELT: .30, LEATHER: .20}

# Rosy, round cheeks blended into the face skin.
y, x = np.mgrid[0:512, 0:512].astype(float) / 511
face_x = (x - .5) * .354
face_z = (y - .5) * .376 + 1.727
blush = (np.exp(-((face_x - .108) / .060) ** 2 - ((face_z - 1.712) / .045) ** 2) +
         np.exp(-((face_x + .108) / .060) ** 2 - ((face_z - 1.712) / .045) ** 2)) * .62
skin_linear = np.array((.80, .42, .30))[None, None, :]
rosy_linear = np.array((.80, .25, .21))[None, None, :]
face_linear = skin_linear * (1 - blush[:, :, None]) + rosy_linear * blush[:, :, None]
face_image = image_file(NAME + '_rosy_cheeks', to_srgb(face_linear))
face_material = bpy.data.materials[FACE]
face_tex = face_material.node_tree.nodes.new('ShaderNodeTexImage')
face_tex.image = face_image
face_material.node_tree.links.new(face_tex.outputs['Color'], face_material.node_tree.nodes['Principled BSDF'].inputs['Base Color'])


# -------------------- skeleton and prop anchors (unchanged from Santa 01)
CUP = Vector((.15, -.48, 1.12))
KETTLE = Vector((-.44, -.40, 1.53))
SHOULDERS = {'L': Vector((.265, 0, 1.43)), 'R': Vector((-.265, 0, 1.43))}
UPPER, LOWER = .31, .30

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
 ('kettle', KETTLE, KETTLE + Vector((0, 0, .12)), 'root'),
 ('cup', CUP, CUP + Vector((0, 0, .12)), 'root'),
 ('liquid', CUP + Vector((0, 0, -.075)), CUP + Vector((0, 0, .025)), 'cup'),
 ('aroma', CUP + Vector((0, 0, .09)), CUP + Vector((0, 0, .19)), 'cup'),
]
POUR_GRIP = Vector((-.18, -.49, 1.73))
POUR_ROT = Matrix.Rotation(math.radians(25), 3, 'Y')
SPOUT_LOCAL = Vector((.44, -.012, -.16))
STREAM_START = POUR_GRIP + POUR_ROT @ SPOUT_LOCAL
BONES.append(('stream', STREAM_START, STREAM_START + Vector((0, 0, -.2)), 'root'))
for side, sign in (('L', 1), ('R', -1)):
    shoulder, elbow, wrist = SHOULDERS[side], elbow_for(side, WRISTS[side]), WRISTS[side]
    BONES += [(f'upper_arm.{side}', shoulder, elbow, 'chest'),
              (f'forearm.{side}', elbow, wrist, f'upper_arm.{side}'),
              (f'hand.{side}', wrist, GRIPS[side], f'forearm.{side}'),
              (f'thigh.{side}', (sign * .16, 0, .86), (sign * .205, 0, .46), 'hips'),
              (f'shin.{side}', (sign * .205, 0, .46), (sign * .225, 0, .12), f'thigh.{side}'),
              (f'foot.{side}', (sign * .225, 0, .12),
               (sign * (.225 + .17 * math.sin(math.radians(14))), -.17 * math.cos(math.radians(14)), .06), f'shin.{side}')]
# Eye bones pivot a little behind each iris (in the head's widened space, see the x1.10/y1.06 scale
# below) and point forward, so rotating them slides the iris across the eye white toward a target.
HEAD_SCALE = Vector((1.10, 1.06, 1))
EYE_PIVOTS = {side: Vector((sign * .062, -.095, 1.789)) * HEAD_SCALE for side, sign in (('L', 1), ('R', -1))}
for side, pivot in EYE_PIVOTS.items():
    BONES.append((f'eye.{side}', pivot, pivot + Vector((0, -.04, 0)), 'head'))
SEG ={name: (Vector(h), Vector(t)) for name, h, t, parent in BONES}
GROUPS = {name: i for i, (name, *_) in enumerate(BONES)}
bm = bmesh.new()
DL = bm.verts.layers.deform.verify()
UV = bm.loops.layers.uv.verify()

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

def ellipsoid(c, r, mat, bones='head', seg=24, rings=14, direction=None, euler=None, lumpy=0):
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
    faces = {face for v in verts for face in v.link_faces}
    if mat == FACE:
        for face in faces:
            for loop in face.loops:
                co = loop.vert.co
                loop[UV].uv = ((co.x / .177 + 1) * .5, (co.z - 1.727) / .376 + .5)
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

def hair_lock(points, radius, bones='head', sides=8, flat=.6, taper=None):
    taper = taper or [.55, .85, 1, 1, .96, .9, .82, .7, .55, .38, .2, .06]
    radii = [radius * taper[min(len(taper) - 1, round(i * (len(taper) - 1) / (len(points) - 1)))] for i in range(len(points))]
    tube(points, radii, HAIR, bones, sides=sides, sub=1, flat=flat)

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

# -------------------- laughing face, glasses, brows and drooping cap
ellipsoid((0, .012, 1.727), (.177, .153, .188), FACE, seg=48, rings=32)
for sign in (-1, 1):
    ellipsoid((sign * .17, .012, 1.735), (.033, .027, .052), SKIN, seg=20, rings=14)
    # Round, raised, rosy cheeks.
    ellipsoid((sign * .108, -.102, 1.720), (.066, .044, .049), FACE, seg=32, rings=20)
    # Wide-open, happy eyes.
    ellipsoid((sign * .066, -.117, 1.788), (.037, .021, .034), WHITE, seg=28, rings=18)
    # Irises are modelled looking straight ahead; their eye bones aim them at the glass each frame.
    eye = 'eye.L' if sign > 0 else 'eye.R'
    ellipsoid((sign * .062, -.135, 1.789), (.020, .009, .023), IRIS, eye, seg=24, rings=14)
    ellipsoid((sign * .062, -.142, 1.790), (.010, .004, .012), BLACK, eye, seg=20, rings=12)
    ellipsoid((sign * .062 - .006, -.146, 1.800), (.005, .0025, .006), WHITE, eye, seg=12, rings=8)
    # Raised upper lids, smile creases under the eyes and crow's feet.
    tube([(sign * .030, -.126, 1.806), (sign * .066, -.140, 1.825), (sign * .102, -.118, 1.809)],
         [.004, .0065, .0035], SKIN, sides=8, sub=4)
    tube([(sign * .036, -.130, 1.762), (sign * .067, -.140, 1.753), (sign * .098, -.124, 1.762)],
         [.003, .005, .003], FACE, sides=8, sub=4)
    for k in range(3):
        tube([(sign * .106, -.110, 1.772 + k * .011), (sign * .124, -.098, 1.768 + k * .016), (sign * .136, -.084, 1.766 + k * .021)],
             [.0018, .0022, .0008], SKIN, sides=6, sub=3)
    # Bushy, arched white eyebrows made of clumps.
    for k in range(7):
        j = lambda s=.004: rng.uniform(-s, s)
        lift = rng.uniform(-.004, .006)
        hair_lock([(sign * (.022 + j()), -.130 + j(.002), 1.838 + lift),
                   (sign * (.050 + j()), -.146 + j(.002), 1.858 + lift + j()),
                   (sign * (.082 + j()), -.141 + j(.002), 1.856 + lift + j()),
                   (sign * (.110 + j()), -.120 + j(.002), 1.836 + lift),
                   (sign * (.130 + j()), -.096, 1.818 + lift)],
                  rng.uniform(.009, .0125), sides=8, flat=.7)
    # Small round wire spectacles.
    torus((sign * .066, -.158, 1.787), (0, 1, 0), .043, .0022, GOLD, sides=48, cross=6, depth=.043)
    tube([(sign * .109, -.152, 1.792), (sign * .169, -.08, 1.798), (sign * .179, .01, 1.783)],
         [.0022] * 3, GOLD, sides=6, sub=3)
tube([(-.023, -.162, 1.795), (0, -.172, 1.800), (.023, -.162, 1.795)], [.0022] * 3, GOLD, sides=6, sub=3)
# Big round red nose.
ellipsoid((0, -.160, 1.733), (.051, .044, .045), ROSY, seg=32, rings=20)

# Open laughing mouth: a D-shaped opening with lips, upper teeth, tongue and a dark cavity.
# A broad grin: wider, deeper, with the corners pulled well up into the cheeks.
MC, MW, MT, MB, MY = 1.644, .066, .011, .044, -.190
def mouth_outline(t, inset=1):
    s = math.sin(t)
    x = MW * math.cos(t) * inset
    z = MC + (MT if s > 0 else MB) * s * inset + .022 * math.cos(t) ** 4
    return Vector((x, MY + .020 * (x / MW) ** 2, z))
ellipsoid((0, -.131, 1.648), (.090, .036, .046), FACE, seg=32, rings=20)
for sign in (-1, 1):
    # Smile creases curving from beside the nose down around the mouth corners.
    tube([(sign * .052, -.170, 1.708), (sign * .078, -.165, 1.682), (sign * .084, -.160, 1.658)],
         [.0025, .0045, .0025], FACE, sides=8, sub=4)
outline = [mouth_outline(TAU * k / 48) for k in range(49)]
tube(outline, [.0055 + .003 * max(0, -math.sin(TAU * k / 48)) for k in range(49)], LIP, sides=8, sub=1, cap=False)
rings = []
for s in (1, .75, .5, .25):
    ring = []
    for k in range(48):
        p = mouth_outline(TAU * k / 48, s)
        ring.append(bm.verts.new(p + Vector((0, .003 + (1 - s) * .016, 0))))
    rings.append(ring)
middle = bm.verts.new(Vector((0, MY + .022, MC - .010)))
for a, b in zip(rings, rings[1:]):
    for k in range(48):
        uv_face((a[k], b[k], b[(k + 1) % 48], a[(k + 1) % 48]), ((0, 0), (0, 1), (1, 1), (1, 0)))
for k in range(48):
    uv_face((rings[-1][k], middle, rings[-1][(k + 1) % 48]), ((0, 0), (.5, 1), (1, 0)))
finish([v for ring in rings for v in ring] + [middle], LAUGH, 'head')
teeth = [mouth_outline(t, .86) + Vector((0, .003, -.004)) for t in [math.pi * (.15 + .7 * k / 12) for k in range(13)]]
tube(teeth, [.003] + [.0075] * 11 + [.003], TEETH, sides=10, sub=1, flat=.45)
ellipsoid((0, MY + .012, MC - .028), (.040, .011, .012), TONGUE, seg=24, rings=12)

# A full, wide beard: shaped underlay plus layered, wavy, flattened locks.
beard_z = [1.25, 1.28, 1.35, 1.42, 1.50, 1.57, 1.63, 1.70]
beard_w = [.03, .09, .16, .20, .222, .222, .21, .18]
beard_y = [-.288, -.239, -.173, -.109, -.053, -.016, -.002, .021]
lathe((0, 0, 0), list(zip(beard_z, beard_w, beard_y)), HAIR, 'head', sides=48, ellipse=.73)
for i in range(230):
    side = rng.uniform(-.98, .98)
    startz = rng.uniform(1.46, 1.71)
    if abs(side) < .45:
        startz = min(startz, 1.596)  # keep the open mouth clear
    endz = max(1.258, startz - rng.uniform(.14, .34))
    phase = rng.uniform(0, TAU); amp = rng.uniform(.006, .013); waves_n = rng.uniform(.9, 1.7)
    points = []
    for j in range(12):
        u = j / 11
        z = startz + (endz - startz) * u
        width = float(np.interp(z, beard_z, beard_w))
        center_y = float(np.interp(z, beard_z, beard_y))
        x = side * width * (1 - .12 * u) + amp * math.sin(u * TAU * waves_n + phase) * math.sin(math.pi * min(1, u * 1.4))
        y = center_y - width * .73 * math.sqrt(max(.03, 1 - (x / max(width, .001)) ** 2)) - .007
        y -= .006 * math.cos(u * TAU * waves_n + phase)
        points.append((x, y, z))
    hair_lock(points, rng.uniform(.011, .019), flat=.55)
# Swept, bushy moustache curling up into the cheeks.
for sign in (-1, 1):
    for k in range(13):
        zb = 1.693 + rng.uniform(-.010, .012); yo = rng.uniform(-.008, .004); droop = rng.uniform(-.007, .007)
        hair_lock([(sign * .006, -.196 + yo, zb + .008), (sign * .040, -.212 + yo, zb - .004 + droop),
                   (sign * .080, -.203 + yo, zb - .009 + droop), (sign * .118, -.178 + yo, zb + .002),
                   (sign * .145, -.144 + yo, zb + .024), (sign * .156, -.120 + yo, zb + .044 + droop)],
                  rng.uniform(.011, .016), sides=9, flat=.75, taper=[.65, 1, 1.05, .9, .55, .15])
    # Hair at the temples, and sideburns joining the hat to the beard.
    ellipsoid((sign * .151, .036, 1.732), (.041, .105, .10), HAIR, seg=20, rings=14)
    for k in range(12):
        dx = rng.uniform(-.006, .008); dy = rng.uniform(-.03, .05)
        hair_lock([(sign * (.166 + dx), .010 + dy, 1.89), (sign * (.183 + dx), -.010 + dy, 1.80),
                   (sign * (.190 + dx), -.030 + dy * .7, 1.74), (sign * (.186 + dx), -.055 + dy * .5, 1.68),
                   (sign * (.178 + dx), -.075 + dy * .3, 1.63)], rng.uniform(.012, .017), flat=.6)
# Cap crown drooping to one side, a plush brim and a big fluffy pompom.
tube([(0, .018, 1.91), (0, .045, 2.04), (.06, .07, 2.12), (.16, .07, 2.12), (.25, .06, 2.04), (.30, .045, 1.92)],
     [.178, .15, .105, .075, .045, .018], RED, 'head', sides=32, sub=4)
fur_ring((0, .012, 1.925), (0, 0, 1), .176, .055, 'head', depth=.152)
ellipsoid((.30, .045, 1.875), (.070, .066, .070), FUR, seg=40, rings=28, lumpy=.07)

# -------------------- arms, tailored sleeves and gripping brown leather gloves
for side in ('L', 'R'):
    shoulder, elbow, wrist = SHOULDERS[side], elbow_for(side, WRISTS[side]), WRISTS[side]
    upper = f'upper_arm.{side}'; fore = f'forearm.{side}'; hand = f'hand.{side}'
    direction = (wrist - elbow).normalized()
    cuff = wrist - direction * .035
    tube([shoulder + (elbow - shoulder) * -.12, shoulder.lerp(elbow, .28), elbow,
          elbow.lerp(cuff, .55), cuff], [.118, .138, .118, .102, .090], RED, [upper, fore], sides=24, sub=3, cloth_folds=.0035)
    fur_ring(cuff, direction, .090, .052, fore)
    for offset in (-.025, .015):
        center = elbow + direction * offset
        torus(center, direction, .113, .006, RED, [upper, fore], sides=24, cross=5)
    if side == 'R':
        ellipsoid(KETTLE + Vector((0, .022, .035)), (.080, .054, .052), LEATHER, hand, seg=24, rings=16)
        for i in range(4):
            x = (i - 1.5) * .030
            s = 1 - .08 * abs(i - 1.5)
            points = [KETTLE + Vector((x, -.002, .062)), KETTLE + Vector((x, -.040 * s, .046)),
                      KETTLE + Vector((x, -.047 * s, .008)), KETTLE + Vector((x, -.025 * s, -.012))]
            tube(points, [.0185, .019, .016, .011], LEATHER, hand, sides=12, sub=3)
            ellipsoid(points[1] + Vector((0, -.008, .004)), (.012, .006, .008), LEATHER, hand, seg=12, rings=8)
        tube([KETTLE + Vector((.079, .012, .035)), KETTLE + Vector((.069, -.024, .005)), KETTLE + Vector((.036, -.039, -.011))],
             [.024, .022, .012], LEATHER, hand, sides=12, sub=3)
    else:
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

# -------------------- golden brass chai kettle with a decorative cartouche
body = KETTLE + Vector((0, 0, -.31))
lathe(body, [(-.14, .105), (-.13, .14), (-.105, .164), (.07, .17), (.105, .155), (.12, .125), (.125, .10)],
      BRASS, 'kettle', sides=56)
for z, r in ((-.12, .149), (.089, .162), (.124, .105)):
    torus(body + Vector((0, 0, z)), (0, 0, 1), r, .0055, GOLD, 'kettle', sides=48, cross=6)
lathe(body, [(.125, .12), (.137, .11), (.156, .072), (.163, .025)], GOLD, 'kettle', sides=40)
ellipsoid(body + Vector((0, 0, .177)), (.026, .026, .022), BRASS, 'kettle', seg=20, rings=12)
spout = [body + Vector((.135, 0, -.04)), body + Vector((.215, -.004, -.015)), body + Vector((.253, -.008, .06)),
         body + Vector((.326, -.012, .13)), KETTLE + SPOUT_LOCAL]
tube(spout, [.038, .031, .024, .018, .015], BRASS, 'kettle', sides=16, sub=4, cap=False)
torus(KETTLE + SPOUT_LOCAL, spout[-1] - spout[-2], .015, .0035, GOLD, 'kettle', sides=24, cross=6)
ellipsoid(KETTLE + SPOUT_LOCAL - (spout[-1] - spout[-2]).normalized() * .006, (.012, .012, .004), MOUTH, 'kettle', seg=16, rings=8,
          direction=spout[-1] - spout[-2])
arc = [KETTLE + Vector((.163 * math.cos(a), 0, -.18 + .18 * math.sin(a))) for a in [math.pi * i / 24 for i in range(25)]]
tube(arc, [.009] * 25, GOLD, 'kettle', sides=8, sub=1)
grip = [KETTLE + Vector((.16 * math.cos(a), 0, -.18 + .18 * math.sin(a))) for a in [math.pi * .30 + math.pi * .40 * i / 16 for i in range(17)]]
tube(grip, [.015] * 17, LEATHER, 'kettle', sides=10, sub=1)
for sign in (-1, 1):
    ellipsoid(KETTLE + Vector((sign * .16, 0, -.18)), (.014, .017, .020), GOLD, 'kettle', seg=16, rings=10)
CW, CH = .125, .078  # cartouche half-width (along the kettle's curve) and half-height
for z in (-.085, .052):
    for k in range(12):
        a = math.pi + math.pi * k / 11
        if abs(.166 * (a - 1.5 * math.pi)) < CW + .014:
            continue  # leave room for the cartouche
        c = body + Vector((.166 * math.cos(a), .166 * math.sin(a), z))
        tangent = Vector((-math.sin(a), math.cos(a), 0))
        points = [c + tangent * (j - .5) * .018 + Vector((0, 0, .006 * math.sin(j * TAU))) for j in (0, .25, .5, .75, 1)]
        tube(points, [.0012] * 5, GOLD, 'kettle', sides=4, sub=1)
# Raised oval cartouche with a beaded border, a kettle-and-glass emblem and "Chaiiwala / of London"
# lettering. Everything is modelled flat on the plane y = -R0 and then wrapped onto the kettle's curve.
R0 = .168
def kettle_radius(z):
    return float(np.interp(z, (-.105, .07), (.164, .17)))
def wrapped(build):
    count = len(bm.verts)
    build()
    bm.verts.ensure_lookup_table()
    for v in bm.verts[count:]:
        rel = v.co - body
        radius = kettle_radius(rel.z)
        d, a = radius + (-rel.y - R0), -math.pi / 2 + rel.x / radius
        v.co = body + Vector((d * math.cos(a), d * math.sin(a), rel.z))

def lettering(text, width, center, shear=0, depth=.0012):
    """Raised text from Blender's built-in font, scaled to `width` and centred on `center`."""
    curve = bpy.data.curves.new('lettering', 'FONT')
    curve.body = text; curve.align_x = 'CENTER'; curve.align_y = 'CENTER'; curve.shear = shear
    ob = bpy.data.objects.new('lettering', curve); scene.collection.objects.link(ob)
    def evaluate():
        bpy.context.view_layer.update()
        return bpy.data.meshes.new_from_object(ob.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    flat = evaluate()
    xs = [v.co.x for v in flat.vertices]
    scale = width / (max(xs) - min(xs))
    bpy.data.meshes.remove(flat)
    curve.size = scale; curve.extrude = depth / 2
    mesh_data = evaluate()
    bpy.data.objects.remove(ob); bpy.data.curves.remove(curve)
    verts = [bm.verts.new(center + Vector((v.co.x, -(v.co.z + depth / 2), v.co.y))) for v in mesh_data.vertices]
    for poly in mesh_data.polygons:
        try:
            uv_face([verts[i] for i in poly.vertices], [(0, 0)] * len(poly.vertices))
        except ValueError:
            pass
    bpy.data.meshes.remove(mesh_data)
    finish(verts, ENGRAVE, 'kettle')

cart = body + Vector((0, -R0, -.012))
face_y = -.0050
wrapped(lambda: ellipsoid(cart, (CW, .005, CH), BRASS, 'kettle', seg=48, rings=16))
wrapped(lambda: torus(cart + Vector((0, face_y, 0)), (0, 1, 0), CW, .0040, GOLD, 'kettle', sides=64, cross=6, depth=CH))
def beads():
    for k in range(40):
        a = TAU * k / 40
        ellipsoid(cart + Vector(((CW - .011) * math.cos(a), face_y - .0015, (CH - .010) * math.sin(a))),
                  (.0026, .0019, .0026), GOLD, 'kettle', seg=8, rings=5)
wrapped(beads)
def emblem():
    # A tiny kettle pouring into a cutting-chai glass, drawn as raised wire lines.
    c = cart + Vector((-.010, face_y - .0008, .036))
    line = lambda pts, r=.0018: tube([c + Vector((px * 2.0, 0, pz * 2.0)) for px, pz in pts], [r] * len(pts), ENGRAVE, 'kettle', sides=6, sub=1)
    ring = [(-.010 + .0085 * math.cos(TAU * k / 16), .0075 * math.sin(TAU * k / 16)) for k in range(17)]
    line(ring)
    line([(-.010 + .0085 * math.cos(math.pi * k / 8), .0075 + .006 * math.sin(math.pi * k / 8)) for k in range(9)])
    line([(-.002, -.002), (.006, .002), (.010, .007)])
    line([(.012, -.009), (.020, -.009), (.022, .004), (.010, .004), (.012, -.009)])
lettering_center = cart + Vector((0, face_y, 0))
wrapped(emblem)
wrapped(lambda: lettering('Chaiiwala', .190, lettering_center + Vector((0, 0, -.008)), shear=.22, depth=.0022))
wrapped(lambda: lettering('of London', .088, lettering_center + Vector((0, 0, -.050)), shear=.15, depth=.0018))

# -------------------- cutting-chai glass, rising chai level and timed stream
profile = [(-.09, .045), (-.085, .05), (.078, .066), (.09, .066), (.09, .062), (.078, .062), (-.078, .047), (-.08, .006)]
lathe(CUP, profile, GLASS, 'cup', sides=48, flute=.0015)
torus(CUP + Vector((0, 0, .089)), (0, 0, 1), .064, .0028, GLASS, 'cup', sides=48, cross=8)
torus(CUP + Vector((0, 0, -.085)), (0, 0, 1), .047, .004, GLASS, 'cup', sides=40, cross=6)
lathe(CUP, [(-.075, .044), (.049, .059), (.052, .058)], CHAI, 'liquid', sides=48, flute=.0004)
end = CUP + Vector((0, 0, .048))
tube([STREAM_START, STREAM_START + Vector((.001, .002, -.065)), end + Vector((.001, 0, .045)), end],
     [.0065, .0075, .007, .006], CHAI, 'stream', sides=9, sub=4)
torus(end, (0, 0, 1), .018, .0024, CHAI, 'stream', sides=24, cross=5)
for i in range(3):
    points = []
    for j in range(10):
        t = j / 9
        points.append(CUP + Vector(((i - 1) * .018 + .009 * math.sin(t * TAU + i),
                                    -.012 + .005 * math.cos(t * TAU + i), .092 + .13 * t)))
    tube(points, [.0012, .0018, .0022, .0024, .0024, .0022, .002, .0016, .001, .0003],
         STEAM, 'aroma', sides=6, sub=1)


# -------------------- object and skin creation
head_groups = [GROUPS[name] for name in ('head', 'eye.L', 'eye.R')]
for vertex in bm.verts:
    if sum(vertex[DL].get(g, 0) for g in head_groups) > .99:
        vertex.co.x *= HEAD_SCALE.x
        vertex.co.y *= HEAD_SCALE.y
bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
# The mouth cavity is an open bowl, so recalc can't tell its inside from its outside. AR Quick Look
# (RealityKit) ignores doubleSided and culls back faces, so make the cavity face the viewer (-y).
laugh_index = next(i for i, m in enumerate(MATS) if m.name == LAUGH)
for face in bm.faces:
    if face.material_index != laugh_index:
        continue
    face.normal_update()
    if face.normal.y > 0:
        face.normal_flip()
mesh = bpy.data.meshes.new(NAME + '_Mesh'); bm.to_mesh(mesh); bm.free()
mesh.update(); mesh.calc_loop_triangles()
character = bpy.data.objects.new(NAME, mesh); scene.collection.objects.link(character)
for mat in MATS: mesh.materials.append(mat)
for name in GROUPS: character.vertex_groups.new(name=name)
arm = bpy.data.armatures.new(NAME + '_Rig')
rig = bpy.data.objects.new(NAME + '_Rig', arm); scene.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig; rig.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
for name, h, t, parent in BONES:
    bone = arm.edit_bones.new(name); bone.head = h; bone.tail = t
    if parent: bone.parent = arm.edit_bones[parent]
bpy.ops.object.mode_set(mode='OBJECT')
character.parent = rig
mod = character.modifiers.new('Armature', 'ARMATURE'); mod.object = rig
for pb in rig.pose.bones: pb.rotation_mode = 'QUATERNION'
assert all(v.groups and abs(sum(g.weight for g in v.groups) - 1) < 1e-4 for v in mesh.vertices)
print(f'[model] {len(mesh.vertices):,} vertices, {len(mesh.loop_triangles):,} triangles, {len(MATS)} materials', flush=True)

# -------------------- bake the hand/prop choreography into ordinary bone keys
def smooth(t): return max(0, min(1, t)) ** 2 * (3 - 2 * max(0, min(1, t)))
def ramp(f, a, b): return smooth((f - a) / (b - a))
def rigid_pose(name, new_head, rotation):
    bone = rig.data.bones[name]
    pose = rig.pose.bones[name]
    pose.matrix = Matrix.Translation(new_head) @ rotation.to_4x4() @ Matrix.Translation(-bone.head_local) @ bone.matrix_local
    bpy.context.view_layer.update()

def orient_segment(name, start, end):
    a, b = SEG[name]
    rigid_pose(name, start, (b - a).rotation_difference(end - start).to_matrix())

def action_fcurves(obj):
    action = obj.animation_data.action
    if hasattr(action, 'fcurves'):  # Blender 4.x
        return action.fcurves
    from bpy_extras.anim_utils import action_get_channelbag_for_slot
    return action_get_channelbag_for_slot(action, obj.animation_data.action_slot).fcurves

EYES = Vector((0, -.13, 1.79))
GAZE = Vector((0, 0, .06))  # look at the chai surface/rim, just above the glass's bone origin
EYE_LIMIT = math.radians(19)  # keeps the iris on the eye white
def look_at_glass(glass, extra_pitch=0):
    """Head turn and nod that follow the glass, as in the photo (the eyes do the rest)."""
    d = glass + GAZE - EYES
    yaw = .6 * math.atan2(d.x, -d.y)
    pitch = .35 * math.atan2(-d.z, math.hypot(d.x, d.y)) + extra_pitch
    # Bone-local Y is the neck axis (turn); local X nods the face forward.
    return Quaternion((0, 1, 0), yaw) @ Quaternion((1, 0, 0), pitch)

def aim_eyes(target):
    """Rotate each eye about its pivot, inside the posed head, so the iris looks at `target`."""
    bpy.context.view_layer.update()
    head = rig.pose.bones['head']
    head_deform = head.matrix @ rig.data.bones['head'].matrix_local.inverted()
    local_target = head_deform.inverted() @ target
    for side, pivot in EYE_PIVOTS.items():
        turn = Vector((0, -1, 0)).rotation_difference((local_target - pivot).normalized())
        if turn.angle > EYE_LIMIT:
            turn = Quaternion(turn.axis, EYE_LIMIT)
        deform = Matrix.Translation(pivot) @ turn.to_matrix().to_4x4() @ Matrix.Translation(-pivot)
        rig.pose.bones[f'eye.{side}'].matrix = head_deform @ deform @ rig.data.bones[f'eye.{side}'].matrix_local
    bpy.context.view_layer.update()

if QUICK:
    rig.pose.bones['head'].rotation_quaternion = look_at_glass(CUP)
    aim_eyes(CUP + GAZE)
if not QUICK:
    mod.show_viewport = False
    for frame in range(1, 301):
        scene.frame_set(frame)
        # Approach -> pour -> lower kettle -> raise upright glass -> smell -> return.
        kettle_amount = ramp(frame, 24, 60) * (1 - ramp(frame, 132, 168))
        cup_amount = ramp(frame, 168, 204) * (1 - ramp(frame, 240, 276))
        kpos = KETTLE.lerp(POUR_GRIP, kettle_amount)
        krot = Matrix.Rotation(math.radians(25) * kettle_amount, 3, 'Y')
        cpos = CUP.lerp(Vector((.030, -.355, 1.590)), cup_amount)
        crot = Matrix.Identity(3)
        rigid_pose('kettle', kpos, krot)
        rigid_pose('cup', cpos, crot)
        for side, pos, rot, origin in (('R', kpos, krot, KETTLE), ('L', cpos, crot, CUP)):
            wrist = pos + rot @ (WRISTS[side] - origin)
            elbow = elbow_for(side, wrist)
            orient_segment(f'upper_arm.{side}', SHOULDERS[side], elbow)
            orient_segment(f'forearm.{side}', elbow, wrist)
            rigid_pose(f'hand.{side}', wrist, rot)
        inhale = math.sin(math.pi * max(0, min(1, (frame - 204) / 36)))
        rig.pose.bones['head'].rotation_quaternion = look_at_glass(cpos, math.radians(1.5 * inhale) * cup_amount)
        aim_eyes(cpos + GAZE)
        warmth = ramp(frame, 128, 148) * (1 - ramp(frame, 270, 298))
        aroma = rig.pose.bones['aroma']
        aroma.scale = (max(.01, warmth), max(.01, warmth * (1 + .06 * math.sin(frame * .12))), max(.01, warmth))
        aroma.rotation_quaternion = Quaternion((0, 1, 0), math.radians(5) * math.sin(frame * .08) * warmth)
        flow = ramp(frame, 62, 66) * (1 - ramp(frame, 125, 129))
        # Keep the glass full while he smells it; empty it only in the final return.
        level = .42 + .58 * ramp(frame, 66, 125) - .58 * ramp(frame, 276, 300)
        surface = CUP.z - .075 + .127 * level
        length = (STREAM_START.z - surface) / (STREAM_START.z - end.z)
        rig.pose.bones['stream'].scale = (max(.01, flow), max(.01, flow * length), max(.01, flow))
        rig.pose.bones['liquid'].scale = (1, level, 1)
        for name in ['kettle', 'cup', 'upper_arm.L', 'forearm.L', 'hand.L', 'upper_arm.R', 'forearm.R', 'hand.R', 'head', 'eye.L', 'eye.R', 'stream', 'liquid', 'aroma']:
            pb = rig.pose.bones[name]
            pb.keyframe_insert('location', frame=frame)
            pb.keyframe_insert('rotation_quaternion', frame=frame)
            pb.keyframe_insert('scale', frame=frame)
    mod.show_viewport = True
    rig.animation_data.action.name = NAME + '_Pour_and_Smell'
    for fc in action_fcurves(rig):
        for k in fc.keyframe_points: k.interpolation = 'LINEAR'
    rig.animation_data.action.use_fake_user = True
    scene.frame_set(1)

# -------------------- studio for editable scene and presentation renders
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
for ob in scene.objects: ob.select_set(False)
rig.select_set(True); bpy.context.view_layer.objects.active = rig
if not QUICK:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, VERSION + '.blend'), compress=True)
    print('[model] Saved packed Blender scene', flush=True)

def render(name, frame, location, target, lens, size):
    scene.frame_set(frame)
    cam.location = location
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens
    scene.render.resolution_x, scene.render.resolution_y = size
    scene.render.filepath = os.path.join(PREVIEWS, VERSION + '-' + name + '.png')
    bpy.ops.render.render(write_still=True)
    print('[render] ' + name, flush=True)

if PREVIEWS:
    os.makedirs(PREVIEWS, exist_ok=True)
    full = ((2.15, -6.3, 2.75), (-.035, -.12, 1.05), 82, (800, 1000))
    render('face', 1, (-.20, -1.60, 1.85), (0, -.04, 1.75), 78, (600, 600))
    # A front view framed like the reference photo.
    render('front', 1, (-.15, -6.6, 1.25), (-.10, -.12, 1.02), 70, (800, 1000))
    render('kettle', 1, (-.36, -1.45, 1.26), (-.43, -.52, 1.21), 85, (600, 600))
    if not QUICK:
        render('fabric', 222, (.85, -1.35, 1.35), (.16, -.19, 1.18), 90, (700, 700))
        for name, frame in [('ready', 1), ('pour', 92), ('aroma', 222)]:
            render(name, frame, *full)
