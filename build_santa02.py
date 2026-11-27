"""Build the Aisle24 edition from the base character made by build_santa_base.py.

blender -b --factory-startup --python-exit-code 1 -P build_santa02.py -- previews
The optional directory receives front and lifted poses and a detail of the tote.
"""
import math
import random
import sys
from contextlib import contextmanager
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import santa_kit as kit  # noqa: E402

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
PHOTO = 'photos/02 Aisle24 Santa.jpg'
# Both cupped gloves support the shopping from opposite sides.
scene, rig, santa = kit.start(2, 'Aisle24', PHOTO, [('groceries', Vector((0, -.41, 1.09)), Vector((0, -.41, 1.27)), 'root'),
    ('bread_idle', Vector((-.185,-.31,1.22)), Vector((-.185,-.31,1.32)), 'groceries'),
    ('greens_idle', Vector((-.225,-.325,1.225)), Vector((-.225,-.325,1.325)), 'groceries')])


def material(name, hex_color, rough=.54, metal=0):
    rgb = [int(hex_color[i:i+2], 16) / 255 for i in (0, 2, 4)]
    linear = [x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4 for x in rgb]
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*linear, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*linear, 1)
    shader.inputs['Roughness'].default_value = rough
    shader.inputs['Metallic'].default_value = metal
    return mat


canvas = material('Cream woven canvas', 'E9D7B7', .96)
seam = material('Canvas binding', 'C8B18F', .89)
navy = material('Midnight blue ink', '163B51')
blue = material('Aisle blue', '168DCA')
white = material('Warm white print', 'FFF7E5')
milk_blue = material('Milk blue', '609FC2')
teal = material('Snack teal', '198CAC', .35)
green = material('Garden green wrapper', '427F37', .35)
sun = material('Golden yellow print', 'FFCD53')
orange = material('Orange peel', 'F49921', .63)
berry = material('Berry print', 'CB4165')
flour = material('Unbleached kraft', 'D6AD7B', .84)
ink = material('Brown ink', '593B2B')
crust = material('Golden baked crust', 'C68542', .74)
crumb = material('Baguette scoring', 'F0C782', .86)
leaf_dark = material('Spinach leaf', '477C29', .46)
leaf_light = material('New leaves', '729936', .47)
vein = material('Leaf vein', '9BB04C', .59)
red = material('Tomato skin', 'D54026', .32)
apple_red = material('Orchard red', 'AC2933', .30)
apple_green = material('Granny Smith', 'A5BA3B', .36)
grape = material('Concord grapes', '673654', .34)
tin = material('Brushed tin', 'B3B8B3', .29, .75)
film = material('Clear_produce_bag', 'F8F6EE', .21)
film.surface_render_method = 'DITHERED'
film.use_transparency_overlap = False
film.node_tree.nodes['Principled BSDF'].inputs['Alpha'].default_value = .095
film.diffuse_color = (*film.diffuse_color[:3], .095)

# A packed, tileable warp/weft texture keeps the canvas recognizable in AR.
y, x = np.mgrid[:128, :128]
warp, weft = np.cos(x * math.tau / 8), np.cos(y * math.tau / 8)
over = ((x // 8 + y // 8) % 2).astype(bool)
fiber = .88 + .10 * np.where(over, warp, weft) + .025 * np.random.default_rng(24).normal(size=x.shape)
canvas_rgb = np.clip(fiber[:, :, None] * np.array([.95, .87, .72]), 0, 1).astype(np.float32)
texture = canvas.node_tree.nodes.new('ShaderNodeTexImage')
texture.image = kit.image('Aisle24 canvas weave', canvas_rgb)
canvas.node_tree.links.new(texture.outputs['Color'], canvas.node_tree.nodes['Principled BSDF'].inputs['Base Color'])

# Bake the artwork into the same weave so the canvas shows through the JPEG's white background.
# The front UVs cover 12 whole weave repeats, starting at tile (-21, 0) in world X/Z.
weave_repeats = 12
weave_tiles_per_meter = 24
front_start_tile = -21
front_rgb = np.tile(canvas_rgb, (weave_repeats, weave_repeats, 1))
source = bpy.data.images.load(str(ROOT / 'photos' / 'aisle24.jpg'))
source_width, source_height = source.size[:]
pixels = np.empty(source_height * source_width * 4, dtype=np.float32)
source.pixels.foreach_get(pixels)
bpy.data.images.remove(source)
# Crop the surrounding white margin before sizing the wordmark. Blender counts rows from the bottom.
logo_rgb = pixels.reshape(source_height, source_width, 4)[326:632, 207:962, :3]
crop_height, crop_width = logo_rgb.shape[:2]
logo_width = 1120
logo_height = round(logo_width * crop_height / crop_width)
rows = np.linspace(0, crop_height - 1, logo_height).round().astype(int)
columns = np.linspace(0, crop_width - 1, logo_width).round().astype(int)
logo_rgb = logo_rgb[rows[:, None], columns]
coverage = np.clip((.98 - logo_rgb.min(axis=2, keepdims=True)) / .60, 0, 1)
left = (front_rgb.shape[1] - logo_width) // 2
bottom = round(.208 * weave_tiles_per_meter * canvas_rgb.shape[0] - logo_height / 2)
print_area = front_rgb[bottom:bottom + logo_height, left:left + logo_width]
print_area[:] = print_area * (1 - coverage) + logo_rgb * coverage
front_canvas = canvas.copy()
front_canvas.name = 'Aisle24 printed canvas'
front_canvas.node_tree.nodes[texture.name].image = kit.image('Aisle24 Market print', front_rgb)

# Assemble the shopping as two rigid vertex groups on the character mesh.
verts, faces, slots, smooth, materials, bones = [], [], [], [], [], []
pose = Matrix.Identity(4)
binding = 'groceries'


@contextmanager
def place(x, y, z, tilt=0, yaw=0, scale=1):
    global pose
    previous = pose
    pose = (pose @ Matrix.Translation((x, y, z)) @ Matrix.Rotation(math.radians(yaw), 4, 'Z')
            @ Matrix.Rotation(math.radians(tilt), 4, 'Y') @ Matrix.Scale(scale, 4))
    try:
        yield
    finally:
        pose = previous


def surface(points, polygons, mat, rounded=False):
    offset = len(verts)
    verts.extend(pose @ Vector(p) for p in points)
    bones.extend([binding] * len(points))
    if mat not in materials:
        materials.append(mat)
    slots.extend([materials.index(mat)] * len(polygons))
    smooth.extend([rounded] * len(polygons))
    faces.extend(tuple(offset + i for i in poly) for poly in polygons)


def rings(rows, mat, rounded=True, close=True):
    n = len(rows[0])
    polys = [(j*n+i, j*n+(i+1)%n, (j+1)*n+(i+1)%n, (j+1)*n+i)
             for j in range(len(rows)-1) for i in range(n)]
    if close:
        polys.extend([tuple(reversed(range(n))), tuple(range((len(rows)-1)*n, len(rows)*n))])
    surface([p for row in rows for p in row], polys, mat, rounded)


def profile(levels, mat, power=1, n=32, rounded=True, close=True):
    rows = []
    for z, w, d in levels:
        row = []
        for i in range(n):
            a = math.tau * i / n
            c, s = math.cos(a), math.sin(a)
            row.append((w * math.copysign(abs(c)**power, c), d * math.copysign(abs(s)**power, s), z))
        rows.append(row)
    rings(rows, mat, rounded, close)


def oval(x, y, z, w, d, h, mat):
    with place(x, y, z):
        profile([(h*math.sin(a), w*max(.008, math.cos(a)), d*max(.008, math.cos(a)))
                 for a in [math.pi*(j/8-.5) for j in range(9)]], mat, n=16)


def cord(points, radius, mat, scales=None):
    path = [Vector(p) for p in points]
    rows = []
    for i, p in enumerate(path):
        axis = (path[min(i+1, len(path)-1)] - path[max(0, i-1)]).normalized()
        guide = Vector((0, 1, 0)) if abs(axis.y) < .95 else Vector((1, 0, 0))
        u = axis.cross(guide).normalized()
        v = axis.cross(u)
        r = radius * (scales[i] if scales else 1)
        rows.append([p + r*(u*math.cos(j*math.tau/8)+v*math.sin(j*math.tau/8)) for j in range(8)])
    rings(rows, mat)


def label(text, x, y, z, width, mat, bold=False):
    font = bpy.data.curves.new('Package type', 'FONT')
    font.resolution_u = 5
    font.body, font.align_x, font.align_y = text, 'CENTER', 'CENTER'
    font.offset = .012 if bold else 0
    ob = bpy.data.objects.new('Typeset', font)
    scene.collection.objects.link(ob)
    bpy.context.view_layer.update()
    evaluated = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    data = evaluated.to_mesh()
    points = [v.co.copy() for v in data.vertices]
    factor = width / (max(v.x for v in points)-min(v.x for v in points))
    surface([(x+p.x*factor, y, z+p.y*factor) for p in points], [tuple(p.vertices) for p in data.polygons], mat)
    evaluated.to_mesh_clear()
    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.curves.remove(font)


def baguette():
    profile([(0,.020,.018),(.025,.049,.043),(.14,.058,.050),(.35,.055,.047),
             (.47,.046,.041),(.50,.034,.032),(.515,.015,.013),(.518,.002,.002)], crust)
    for z in (.13,.24,.35,.435):
        # Taper the slash to two sharp points and curve it over the loaf.
        pts = []
        for k in range(13):
            t = k/12
            px = (t-.5)*.056
            py = -(.048 if z < .4 else .044) * math.sqrt(1-(px/.055)**2) - .002
            pts.extend([(px,py,z+(t-.5)*.073+side*.010*math.sin(t*math.pi)) for side in (-1,1)])
        surface(pts, [(2*k,2*k+2,2*k+3,2*k+1) for k in range(12)], crumb)


def spinach():
    for i, (angle, length) in enumerate([(-49,.29),(-30,.32),(-12,.33),(8,.28),(32,.25),(-23,.23)]):
        with place(0, -.008*i, 0, angle, (i%3-1)*18):
            pts, mid = [], []
            for j in range(13):
                t = j/12
                w = .056*math.sin(math.pi*t)**.8*(1+.07*math.sin(t*28))
                z = t*length
                depth = -.038*t*t
                pts.extend([(-w,depth+.014*math.sin(t*math.pi),z),(0,depth,z),(w,depth+.014*math.sin(t*math.pi),z)])
                mid.append((0,depth-.001,z))
            surface(pts, [(3*j+k,3*j+k+1,3*j+k+4,3*j+k+3) for j in range(12) for k in (0,1)],
                    leaf_dark if i%2==0 else leaf_light, True)
            cord(mid,.0018,vein,[1-.85*j/12 for j in range(13)])
            for t in (.30,.47,.64):
                for s in (-1,1):
                    cord([(0,-.038*t*t-.001,t*length),(s*.042,-.038*(t+.12)**2+.008,(t+.12)*length)],.001,vein)


def fruit(x, y, z, r, mat, tomato=False):
    with place(x,y,z):
        rows = []
        for h,w in [(-.91,.24),(-.82,.59),(-.47,.89),(0,1),(.48,.96),(.76,.72),(.81,.43),(.66,.08)]:
            row = []
            for j in range(32):
                a = math.tau*j/32
                lobe = math.cos(5*a)*h*h
                radius = r*w*(1+.045*lobe)
                row.append((radius*math.cos(a),radius*.97*math.sin(a),r*(h+.035*lobe)))
            rows.append(row)
        rings(rows,mat)
        cord([(0,0,r*.67),(.003,.001,r*.92),(.007,0,r*1.10)],.0026,ink)
        if tomato:
            for i in range(5):
                with place(0,0,r*.78,yaw=i*72):
                    surface([(0,-.008,0),(.012,0,.001),(0,.033,-.004),(-.006,.009,.001)],[(0,1,2,3)],leaf_dark)


def packet(mat, title):
    profile([(0,.080,.016),(.009,.080,.021),(.04,.071,.041),(.13,.074,.044),
             (.19,.082,.029),(.206,.086,.009),(.219,.086,.008)],mat,.29)
    for z in (.207,.213,.218):
        cord([(-.083,-.008,z),(0,-.010,z),(.083,-.008,z)],.0012,white)
    label('AISLE 24',0,-.038,.176,.065,white)
    label(title,0,-.045,.135,.130,sun,True)
    for x,z in [(-.034,.062),(0,.078),(.036,.053)]:
        oval(x,-.042,z,.026,.005,.020,sun)


def milk():
    w,d=.066,.051
    profile([(0,w,d),(.010,w,d),(.23,w,d),(.277,w,.005),(.291,w,.005)],white,.10)
    profile([(.002,w+.0006,d+.0006),(.065,w+.0006,d+.0006)],milk_blue,.10)
    label('MILK',0,-d-.001,.159,.104,navy,True)
    label('FARM FRESH',0,-d-.001,.120,.083,blue)
    label('1 L',0,-d-.001,.035,.032,white)
    oval(-.025,-.028,.261,.023,.014,.016,milk_blue)


def flour_bag():
    profile([(0,.072,.041),(.012,.082,.050),(.14,.076,.049),(.177,.069,.036),
             (.208,.070,.016),(.221,.076,.019)], flour,.28)
    with place(0,-.003,.219):
        profile([(-.009,.077,.020),(.004,.080,.022),(.010,.077,.018)],crust,.24)
    label('STONE GROUND',0,-.050,.142,.103,ink)
    label('FLOUR',0,-.051,.108,.127,ink,True)
    for z in (.082,.132):
        cord([(-.061,-.050,z),(.061,-.050,z)],.0013,ink)
    label('ALL PURPOSE',0,-.051,.062,.080,ink)


def yogurt():
    profile([(0,.037,.037),(.008,.040,.040),(.072,.052,.052),(.079,.052,.052)], white)
    profile([(.015,.042,.042),(.029,.045,.045)],berry)
    profile([(.078,.054,.054),(.082,.055,.055)],milk_blue,.28)
    oval(0,0,.083,.021,.018,.002,berry)
    label('DAIRY',0,-.049,.054,.043,navy,True)


# Rear row gives the bundle its stepped silhouette. The fruit and flour sit
# forward, where the curled fingers wrap around the outer edges.
binding = 'bread_idle'
with place(-.185,-.31,1.22,-17,scale=.92):
    baguette()
binding = 'greens_idle'
with place(-.225,-.325,1.225,-10,scale=.94):
    spinach()
binding = 'groceries'
with place(.070,-.292,1.245,4,scale=1.14):
    packet(teal,'SNACKS')
with place(.215,-.270,1.265,19,scale=1.16):
    packet(green,'CHIPS')
with place(.215,-.363,1.195,10):
    milk()
fruit(-.105,-.385,1.325,.070,red,True)
fruit(-.007,-.335,1.305,.061,red,True)
for z in (1.077,1.157,1.237):
    for x,y in [(-.238,-.435),(-.155,-.392)]:
        with place(x,y,z,-6):
            yogurt()
with place(.113,-.469,1.075,-5,scale=1.05):
    flour_bag()
for x,y,z,r,mat in [(-.112,-.488,1.115,.048,apple_red),(-.037,-.503,1.107,.051,apple_green),
        (.038,-.488,1.121,.047,orange),(-.117,-.462,1.188,.048,apple_green),
        (-.051,-.491,1.203,.052,apple_red),(.015,-.455,1.195,.048,apple_green)]:
    fruit(x,y,z,r,mat)
with place(-.041,-.477,1.055):
    rows = []
    for z,w,d,fold in [(0,.080,.040,.06),(.014,.122,.057,.04),(.061,.134,.082,.025),
                        (.124,.128,.080,.03),(.177,.100,.062,.06),(.225,.019,.012,.15),
                        (.232,.015,.010,.10),(.277,.055,.034,.22)]:
        row = []
        for j in range(64):
            a = math.tau*j/64
            wrinkle = 1+fold*math.sin(12*a+.7*z)
            row.append((w*wrinkle*math.cos(a),d*wrinkle*math.sin(a),z))
        rows.append(row)
    rings(rows,film,close=False)
    with place(0,0,.227):
        profile([(0,.020,.014),(.009,.019,.014)],red)

# Open canvas tote with gussets, bound top edge and two continuous web handles.
binding = 'root'
with place(-.635,.008,.009,yaw=8):
    levels = [(0,.183,.083),(.018,.209,.099),(.28,.223,.106),(.454,.230,.114)]
    shell_start = len(faces)
    profile(levels,canvas,.24,48,close=False)
    tote_shell = range(shell_start, len(faces))
    profile([(.450,.230,.114),(.459,.231,.115),(.462,.224,.108),(.426,.221,.106)],seam,.24,48,close=False)
    profile([(.017,.201,.092),(.023,.202,.093)],seam,.24)
    for side in (-1,1):
        cord([(side*.176,-.079,.009),(side*.200,-.088,.24),(side*.207,-.090,.45)],.0032,seam)
    for s in (-1,1):
        rows=[]
        for i in range(33):
            a = math.pi*i/32
            x,z=.113*math.cos(a),.453-.142*math.sin(a)
            y=s*(.115+.016*math.sin(a))
            rows.append([(x+dx*.010*math.cos(a),y+dy*.002,z-dx*.010*math.sin(a))
                         for dx,dy in [(-1,-1),(1,-1),(1,1),(-1,1)]])
        rings(rows,canvas)
    with place(-.124,.034,.365,-17,scale=.72):
        baguette()
    with place(.015,.052,.390,-5,scale=.78):
        packet(berry,'BITES')
    with place(.113,.031,.402,13,scale=.75):
        packet(teal,'CHIPS')
    with place(-.130,.012,.414,scale=.45):
        spinach()
    for i in range(3):
        x=.060+i*.024
        path=[(x-.038,-.051,.447),(x-.012,-.053,.459),(x+.014,-.045,.484),
              (x+.032,-.036,.516+i*.005),(x+.038,-.028,.546+i*.005)]
        cord(path,.015,sun,[.23,.88,1,.72,.24])
        cord([path[-1],(x+.035,-.027,.557+i*.005)],.004,ink,[1,.7])
    for i,(x,mat) in enumerate([(.027,red),(.112,green)]):
        with place(x,-.039,.401+.012*i):
            profile([(0,.033,.033),(.083,.033,.033)],mat)
            profile([(.081,.034,.034),(.086,.034,.034)],tin)
            oval(0,-.004,.087,.011,.005,.0015,navy)
    rand=random.Random(24)
    for layer,count in enumerate((7,6,3)):
        for i in range(count):
            a=math.tau*i/count
            oval(-.085+(.052-.012*layer)*math.cos(a),-.032+.028*math.sin(a),
                 .459+layer*.024+rand.uniform(-.006,.006),.023,.021,.022,grape)

shopping = bpy.data.meshes.new('Aisle24 shopping')
shopping.from_pydata(verts, [], faces)
shopping.update()
props = bpy.data.objects.new('Shopping',shopping)
scene.collection.objects.link(props)
for mat in materials:
    shopping.materials.append(mat)
front_canvas_slot = len(shopping.materials)
shopping.materials.append(front_canvas)
uv = shopping.uv_layers.new(name=santa.data.uv_layers.active.name, do_init=False)
uv.uv.foreach_set('vector', np.zeros(len(shopping.loops)*2, dtype=np.float32))
for poly, slot, rounded in zip(shopping.polygons, slots, smooth):
    poly.material_index, poly.use_smooth = slot, rounded
    if materials[slot] == canvas:
        if poly.index in tote_shell and poly.normal.y < -.9:
            poly.material_index = front_canvas_slot
            for loop in poly.loop_indices:
                x, _, z = shopping.vertices[shopping.loops[loop].vertex_index].co
                uv.data[loop].uv = ((x * weave_tiles_per_meter - front_start_tile) / weave_repeats,
                                    z * weave_tiles_per_meter / weave_repeats)
            continue
        a, b = sorted(sorted(range(3), key=lambda k: abs(poly.normal[k]))[:2])
        for loop in poly.loop_indices:
            co = shopping.vertices[shopping.loops[loop].vertex_index].co
            uv.data[loop].uv = (co[a] * weave_tiles_per_meter, co[b] * weave_tiles_per_meter)
for name in ('groceries','bread_idle','greens_idle','root'):
    props.vertex_groups.new(name=name).add([i for i,bone in enumerate(bones) if bone==name],1,'REPLACE')
bpy.ops.object.select_all(action='DESELECT')
props.select_set(True)
santa.select_set(True)
bpy.context.view_layer.objects.active=santa
bpy.ops.object.join()


def clean_elbow_seams():
    """Remove only the detached decorative elbow rings from this edition's base mesh.

    The shared model creates each ring with 24 x 5 vertices. Match topology,
    red fabric, arm-only skin weights and the rest elbow position before deleting.
    """
    import bmesh
    obj = santa
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    layer = bm.verts.layers.deform.active
    names = {g.index: g.name for g in obj.vertex_groups}
    visited = set()
    remove = []
    count = 0
    if layer is not None:
        for seed in bm.verts:
            if seed in visited:
                continue
            stack, component = [seed], []
            visited.add(seed)
            while stack:
                v = stack.pop()
                component.append(v)
                for edge in v.link_edges:
                    other = edge.other_vert(v)
                    if other not in visited:
                        visited.add(other)
                        stack.append(other)
            if len(component) != 120 or any(len(v.link_edges) != 4 for v in component):
                continue
            faces = {f for v in component for f in v.link_faces}
            if len(faces) != 120 or any(len(f.verts) != 4 or obj.data.materials[f.material_index].name != 'Crimson_velvet' for f in faces):
                continue
            owners = {names.get(i) for v in component for i, w in v[layer].items() if w > .001}
            centre = sum((v.co for v in component), Vector((0, 0, 0))) / len(component)
            for side in ('L', 'R'):
                allowed = {n + '.' + side for n in ('upper_arm', 'forearm', 'sleeve_sway')}
                elbow = rig.data.bones['forearm.' + side].head_local
                if owners and owners <= allowed and (centre - elbow).length < .055:
                    remove.extend(component)
                    count += 1
                    break
    if remove:
        bmesh.ops.delete(bm, geom=remove, context='VERTS')
        bm.to_mesh(obj.data)
        obj.data.update()
    bm.free()
    print(f'[Santa02] Removed {count} detached elbow seam rings (expected 4).', flush=True)


clean_elbow_seams()


# Ten-second shopping idle. Original side-grip carry with small asymmetry and secondary motion.
FRAMES = 241
kit.santa_motion.BODY_TILT_DEG = 3.0
kit.santa_motion.CLOTHING_SWAY_DEG = 3.5
kit.santa_motion.FOOT_ADJUST_DEG = 1.25
kit.santa_motion.HAT_FOLLOW_DEG = 4.0


def ease(t, a, b):
    u = max(0.0, min(1.0, (t-a)/(b-a)))
    return u**3 * (10 + u*(-15 + 6*u))


def pulse(t, a, b, c, d):
    return ease(t,a,b)*(1-ease(t,c,d))


def activity(t):
    return pulse(t,.16,.32,.65,.80)


def shared_reachable_delta(delta, wrists):
    # Move the bundle and both wrists together, never clamp hands separately.
    constraints = []
    for side, wrist in wrists.items():
        upper = rig.data.bones['upper_arm.'+side]
        fore = rig.data.bones['forearm.'+side]
        constraints.append((kit.attached(upper.name)-wrist,
                            upper.length+fore.length-.012))
    delta = delta.copy()
    for _ in range(100):
        for anchor, limit in constraints:
            v = delta-anchor
            if v.length > limit:
                delta = anchor+v.normalized()*limit
        if all((delta-a).length <= r+1e-6 for a,r in constraints):
            return delta
    raise RuntimeError('Grocery arm reach constraints do not overlap')


def relaxed_reach(side, wrist):
    # Same two-link geometry as the original reach, with a modest outward elbow bias.
    upper, fore = (rig.data.bones[n+'.'+side] for n in ('upper_arm','forearm'))
    shoulder = kit.attached(upper.name)
    v = wrist - shoulder
    d = v.length
    if not abs(upper.length-fore.length)+.001 < d < upper.length+fore.length-.005:
        kit.reach(side, wrist)
        return
    direction = v/d
    along = (upper.length**2-fore.length**2+d*d)/(2*d)
    sign = 1 if side == 'L' else -1
    guide = Vector((1.12*sign, .04, -.60))
    pole = guide-direction*guide.dot(direction)
    if pole.length < 1e-6:
        kit.reach(side,wrist)
        return
    elbow = shoulder+direction*along+pole.normalized()*math.sqrt(max(0,upper.length**2-along**2))
    for bone,a,b in ((upper,shoulder,elbow),(fore,elbow,wrist)):
        kit.rigid(bone.name,a,(bone.tail_local-bone.head_local).rotation_difference(b-a).to_matrix())


def pose_at(t):
    phase = math.tau*(0.0 if t >= 1 else t)
    lift = activity(t)
    prep = pulse(t,.12,.16,.18,.27)
    glance = pulse(t,.10,.22,.45,.55)
    scan = pulse(t,.32,.36,.40,.45)
    nod = pulse(t,.55,.59,.61,.65)
    breathe = math.sin(2*phase)
    # Small chest-local pitch layered on the shared planted body sway.
    chest = rig.pose.bones['chest']
    axis = chest.bone.matrix_local.to_3x3().inverted() @ Vector((1,0,0))
    chest.rotation_quaternion = chest.rotation_quaternion @ Quaternion(
        axis.normalized(), math.radians(-.65 - .7*lift + .35*prep + .45*breathe))
    bpy.context.view_layer.update()
    # Preserve the original side grips. Lower the entire carry and use a tiny
    # roll to make one supporting hand slightly lower than the other.
    pivot = rig.data.bones['groceries'].head_local.copy()
    settle = pulse(t,.32,.35,.37,.43)
    roll = math.radians(1.6 + .5*math.sin(phase) + .5*lift)
    rotation = Matrix.Rotation(roll,3,'Y')
    delta = Vector((.008*math.sin(phase), -.008-.006*lift,
                    -.035+.065*lift-.010*prep+.003*breathe-.003*settle))
    wrists = {side: pivot+rotation@(Vector((sign*.322,-.415,1.125))-pivot)
              for side,sign in [('L',1),('R',-1)]}
    delta = shared_reachable_delta(delta, wrists)
    kit.rigid('groceries',pivot+delta,rotation)
    for side,wrist in wrists.items():
        relaxed_reach(side,wrist+delta)
        kit.rigid('hand.'+side,wrist+delta,rotation)
    # Child bones rotate locally around the base of the bread and leaves.
    # Their motion is small and fades after the lift; all heavier food stays rigid.
    flutter = pulse(t,.28,.34,.36,.46)*math.sin(8*phase)
    for name,amount in (('bread_idle',.65),('greens_idle',1.5)):
        pb = rig.pose.bones[name]
        pb.rotation_quaternion = Quaternion((1,0,0),math.radians(amount*(.35*math.sin(phase)+flutter)))
    # Preserve the original head axes/signs; use a deliberate scan and soft nod.
    rig.pose.bones['head'].rotation_quaternion = (
        Quaternion((0,1,0), -.035-.095*glance+.065*scan)
        @ Quaternion((1,0,0), .025+.16*glance+.055*nod))
    eye_glance = pulse(t,.08,.19,.44,.53)
    for side in ('L','R'):
        rig.pose.bones['eye.'+side].rotation_quaternion = Quaternion(
            (1,0,0),-min(.025+.13*eye_glance,kit.EYE_DOWN_LIMIT))


kit.bake('Santa02_Grocery_Lift', FRAMES, pose_at,
         ['groceries','bread_idle','greens_idle','head','eye.L','eye.R']+[n+'.'+s for s in 'LR' for n in ('upper_arm','forearm','hand')],
         activity=activity)


def tuck_beard(margin=.008, floor=.006, hold=.012, radius=.045, cell=.004):
    """Tuck the lower beard in behind the shopping, which the photo shows held in front of it.

    On every frame of the loop each draped beard vertex should sit `margin` behind the back of any
    shopping on its front-to-back line and `floor` in front of the coat. Its depth in front of the
    coat (at the tightest frame) is scaled by k: 1 keeps the modelled beard, 0 lays it on the coat.
    k varies smoothly with height and width only, holding its value for `hold` before easing back to
    1 over `radius`, so each lock keeps its layering and bends in behind the shopping. Where the
    shopping sinks into the coat there is no room: that beard lies on the coat, or goes back into it
    far enough not to show in front of the shopping, and is removed where the shopping hides it on
    every frame."""
    mesh = santa.data
    n = len(mesh.vertices)
    rest = np.empty(n * 3)
    mesh.vertices.foreach_get('co', rest)
    rest = rest.reshape(n, 3)
    names = {g.index: g.name for g in santa.vertex_groups}
    shop, torso, drape = np.zeros(n, bool), np.zeros(n, bool), np.zeros(n, bool)
    for v in mesh.vertices:
        weights = {names[g.group]: g.weight for g in v.groups}
        shop[v.index] = sum(weights.get(b, 0) for b in ('groceries', 'bread_idle', 'greens_idle')) > .5
        torso[v.index] = sum(weights.get(b, 0) for b in ('hips', 'spine', 'chest', 'neck')) > .98
        drape[v.index] = weights.get(kit.BEARD_BONE, 0) > 0
    beard_slot = mesh.materials.find('Silver_beard')
    coat_slots = {mesh.materials.find(m) for m in ('Crimson_velvet', 'Ivory_plush_fur')}
    shop_faces = [tuple(f.vertices) for f in mesh.polygons if shop[list(f.vertices)].all()]
    coat_faces = [tuple(f.vertices) for f in mesh.polygons
                  if f.material_index in coat_slots and torso[list(f.vertices)].all()]
    beard_faces = [tuple(f.vertices) for f in mesh.polygons
                   if f.material_index == beard_slot and drape[list(f.vertices)].any()]
    beard = np.array(sorted({i for f in beard_faces for i in f if drape[i]}))
    slot = np.full(n, -1)
    slot[beard] = np.arange(len(beard))

    def tree(co, faces):
        used = sorted({i for f in faces for i in f})
        index = {i: k for k, i in enumerate(used)}
        return BVHTree.FromPolygons([Vector(co[i]) for i in used], [[index[i] for i in f] for f in faces])

    # The armature blends the head and the drape linearly, so pushing a vertex back along the rest
    # pose's +y moves it along the same blend of those bones' +y axes on every frame.
    bones = ('head', kit.BEARD_BONE)
    weight = np.zeros((len(beard), len(bones)))
    for k, i in enumerate(beard):
        for g in mesh.vertices[i].groups:
            if names[g.group] in bones:
                weight[k, bones.index(names[g.group])] = g.weight
    need = np.full(len(beard), -np.inf)   # push that clears the back of the shopping
    ahead = np.full(len(beard), -np.inf)  # push that reaches the front of the shopping
    depth = np.full(len(beard), np.inf)   # room in front of the coat at the tightest frame
    covered = np.zeros(len(beard), int)
    posed = np.empty(n * 3)
    for frame in range(1, FRAMES + 1):
        scene.frame_set(frame)
        santa.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.vertices.foreach_get('co', posed)
        co = posed.reshape(n, 3)
        shopping, coat = tree(co, shop_faces), tree(co, coat_faces)
        axes = np.array([(rig.pose.bones[b].matrix @ rig.data.bones[b].matrix_local.inverted()).col[1][:3]
                         for b in bones])
        push = weight @ axes
        rate = np.linalg.norm(push, axis=1)  # distance moved per unit of push
        push /= rate[:, None]
        for k, i in enumerate(beard):
            p, e = Vector(co[i]), Vector(push[k])
            behind = shopping.ray_cast(p + e, -e, 3)[0]
            if behind is not None:
                covered[k] += 1
                need[k] = max(need[k], ((behind - p).dot(e) + margin) / rate[k])
                ahead[k] = max(ahead[k], (shopping.ray_cast(p - e, e, 3)[0] - p).dot(e) / rate[k])
            front = coat.ray_cast(p - e, e, 3)[0]
            if front is not None:
                depth[k] = min(depth[k], (front - p).dot(e) / rate[k])
    scene.frame_set(1)
    # A face moves back as one piece, so each vertex clears what its neighbours must clear, and is
    # only removed if the shopping hides all of its faces on every frame.
    own_need, always = need.copy(), covered == FRAMES
    hidden = always.copy()
    for face in beard_faces:
        ks = slot[[i for i in face if slot[i] >= 0]]
        need[ks] = np.maximum(need[ks], own_need[ks].max())
        hidden[ks] &= always[ks].all()
    room = depth > floor
    depth = np.where(np.isinf(depth), np.maximum(need, 0) + .1, depth)  # no coat behind: push freely
    most = depth - floor  # the furthest push that keeps the vertex in front of the coat
    blocked = (need > 0) & (need > most)
    remove = blocked & hidden & (ahead > most)
    k_hi = np.where((need > 0) & room, 1 - need / depth, 1.0)
    k_lo = np.where(room, floor / depth, 1.0)
    # Smooth k over height and width: the lowest k within reach, easing back to 1 with distance.
    x, z = rest[beard, 0], rest[beard, 2]
    x0, z0 = x.min() - radius - cell, z.min() - radius - cell
    shape = (int((z.max() + radius - z0) / cell) + 3, int((x.max() + radius - x0) / cell) + 3)
    target = np.ones(shape)
    np.minimum.at(target, (((z - z0) / cell).astype(int), ((x - x0) / cell).astype(int)),
                  np.clip(np.where(blocked, 0, k_hi), 0, 1))
    field = target.copy()
    reach = int(radius / cell) + 1
    for dr in range(-reach, reach + 1):
        for dc in range(-reach, reach + 1):
            d = math.hypot(dr, dc) * cell
            if d >= radius or dr == dc == 0:
                continue
            t = max(0.0, (d - hold) / (radius - hold))
            shifted = np.ones(shape)
            shifted[max(dr, 0):shape[0] + min(dr, 0), max(dc, 0):shape[1] + min(dc, 0)] = \
                target[max(-dr, 0):shape[0] + min(-dr, 0), max(-dc, 0):shape[1] + min(-dc, 0)]
            field = np.minimum(field, shifted + (1 - shifted) * t * t * (3 - 2 * t))
    fx, fz = (x - x0) / cell - .5, (z - z0) / cell - .5
    c, r = np.floor(fx).astype(int), np.floor(fz).astype(int)
    tx, tz = fx - c, fz - r
    k = (field[r, c] * (1 - tx) * (1 - tz) + field[r, c + 1] * tx * (1 - tz)
         + field[r + 1, c] * (1 - tx) * tz + field[r + 1, c + 1] * tx * tz)
    k = np.maximum(np.minimum(k, k_hi), k_lo)
    push = np.where(room, depth * (1 - k), 0.0)
    push = np.where(blocked, np.maximum(np.maximum(most, 0), np.minimum(need, ahead + margin)), push)
    push[remove] = 0
    rest[beard, 1] += push
    mesh.vertices.foreach_set('co', rest.ravel())
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.verts[i] for i in beard[remove]], context='VERTS')
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    print(f'[Santa02] Tucked the beard behind the shopping: moved {(push > 0).sum()} vertices '
          f'({(blocked & ~remove).sum()} onto the coat), removed {remove.sum()} always hidden.', flush=True)


tuck_beard()
cam=scene.camera


def camera(location,target,lens,size):
    cam.location=location
    cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler()
    cam.data.lens=lens
    scene.render.resolution_x,scene.render.resolution_y=size


def front():
    camera((-.30,-5.85,1.98),(-.175,-.03,1.06),77,(800,900))


front()
scene.render.resolution_percentage=100
scene.render.engine='CYCLES'
scene.cycles.samples=20
scene.cycles.use_denoising=True
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'santa02.blend'),compress=True)
if ARGS:
    previews=Path(ARGS[0]).resolve()
    previews.mkdir(exist_ok=True,parents=True)
    for name,frame in [('front',1),('lift',89),('tote',1)]:
        if name=='tote':
            camera((-.97,-2.13,.96),(-.64,0,.37),82,(640,640))
        scene.frame_set(frame)
        scene.render.filepath=str(previews/('santa02-'+name+'.png'))
        bpy.ops.render.render(write_still=True)
        if name=='front':
            scene.render.image_settings.file_format='WEBP'
            scene.render.image_settings.quality=88
            bpy.data.images['Render Result'].save_render(str(ROOT/'docs'/'santa02-poster.webp'),scene=scene)
            scene.render.image_settings.file_format='PNG'
