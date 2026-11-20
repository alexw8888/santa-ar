"""Build the Aisle24 edition from the packed character made by build_santa01.py.

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

ROOT = Path(__file__).resolve().parent
ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
PHOTO = 'photos/02 Aisle24 Santa.jpg'
bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'santa01.blend'))
scene = bpy.context.scene
scene.name = 'Aisle24'
scene['Reference'] = PHOTO
scene.frame_start, scene.frame_end = 1, 121
rig = bpy.data.objects['Santa01_Rig']
santa = bpy.data.objects['Santa01']
rig.animation_data_clear()
rig.name = rig.data.name = 'Santa02_Rig'
santa.name, santa.data.name = 'Santa02', 'Santa02_Mesh'
for bone in rig.pose.bones:
    bone.matrix_basis = Matrix.Identity(4)

# Keep the original tailoring and skin weights. Mirror the cupped glove for the
# second hand so both palms can support the shopping from opposite sides.
tea = ('cup', 'liquid', 'aroma', 'stream', 'kettle')
mesh = bmesh.new()
mesh.from_mesh(santa.data)
skin = mesh.verts.layers.deform.active
groups = santa.vertex_groups
discard = {groups[n].index for n in (*tea, 'hand.R')}
bmesh.ops.delete(mesh, geom=[v for v in mesh.verts if discard.intersection(v[skin].keys())], context='VERTS')
left = groups['hand.L'].index
right = groups['hand.R'].index
left_bind = rig.data.bones['hand.L'].head_local.copy()
right_bind = rig.data.bones['hand.R'].head_local.copy()
glove = [f for f in mesh.faces if all(v[skin].get(left, 0) > .999 for v in f.verts)]
copy = bmesh.ops.duplicate(mesh, geom=glove)['geom']
for v in (item for item in copy if isinstance(item, bmesh.types.BMVert)):
    p = v.co - left_bind
    v.co = right_bind + Vector((-p.x, p.y, p.z))
    del v[skin][left]
    v[skin][right] = 1
bmesh.ops.reverse_faces(mesh, faces=[f for f in copy if isinstance(f, bmesh.types.BMFace)])
mesh.to_mesh(santa.data)
mesh.free()
for name in tea:
    groups.remove(groups[name])
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode='EDIT')
for name in tea:
    rig.data.edit_bones.remove(rig.data.edit_bones[name])
load = rig.data.edit_bones.new('groceries')
load.head, load.tail = (0, -.41, 1.09), (0, -.41, 1.27)
load.parent = rig.data.edit_bones['root']
bpy.ops.object.mode_set(mode='OBJECT')
used = {p.material_index for p in santa.data.polygons}
for i in reversed(range(len(santa.data.materials))):
    if i not in used:
        santa.data.materials.pop(index=i)
for action in list(bpy.data.actions):
    if action.users <= int(action.use_fake_user):
        bpy.data.actions.remove(action)
bpy.data.orphans_purge(do_recursive=True)


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


canvas = material('Honey woven canvas', 'BC9465', .96)
seam = material('Canvas binding', '97704A', .89)
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
pixels = np.ones((128, 128, 4), dtype=np.float32)
pixels[:, :, :3] = fiber[:, :, None] * np.array([.75, .59, .40])
swatch = bpy.data.images.new('Aisle24 canvas weave', width=128, height=128, alpha=False)
swatch.pixels.foreach_set(pixels.ravel())
swatch.pack()
texture = canvas.node_tree.nodes.new('ShaderNodeTexImage')
texture.image = swatch
canvas.node_tree.links.new(texture.outputs['Color'], canvas.node_tree.nodes['Principled BSDF'].inputs['Base Color'])

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
with place(-.185,-.31,1.27,-17):
    baguette()
with place(-.225,-.325,1.275,-10):
    spinach()
with place(.092,-.292,1.29,4,scale=1.20):
    packet(teal,'SNACKS')
with place(.236,-.250,1.32,24,scale=1.24):
    packet(green,'CHIPS')
with place(.225,-.363,1.24,13):
    milk()
fruit(-.105,-.368,1.365,.070,red,True)
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
    profile(levels,canvas,.24,48,close=False)
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
    label('Aisle',-.051,-.110,.199,.174,white,True)
    label('24',.091,-.110,.199,.101,blue,True)
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
uv = shopping.uv_layers.new(name=santa.data.uv_layers.active.name, do_init=False)
uv.uv.foreach_set('vector', np.zeros(len(shopping.loops)*2, dtype=np.float32))
for poly, slot, rounded in zip(shopping.polygons, slots, smooth):
    poly.material_index, poly.use_smooth = slot, rounded
    if materials[slot] == canvas:
        a,b = sorted(range(3),key=lambda k: abs(poly.normal[k]))[:2]
        a,b = sorted((a,b))
        for loop in poly.loop_indices:
            co=shopping.vertices[shopping.loops[loop].vertex_index].co
            uv.data[loop].uv=(co[a]*24,co[b]*24)
for name in ('groceries','root'):
    props.vertex_groups.new(name=name).add([i for i,bone in enumerate(bones) if bone==name],1,'REPLACE')
bpy.ops.object.select_all(action='DESELECT')
props.select_set(True)
santa.select_set(True)
bpy.context.view_layer.objects.active=santa
bpy.ops.object.join()


def rigid(name, point, rotation):
    bone=rig.data.bones[name]
    rig.pose.bones[name].matrix=(Matrix.Translation(point) @ rotation.to_4x4()
        @ Matrix.Translation(-bone.head_local) @ bone.matrix_local)
    bpy.context.view_layer.update()


def bend_arm(side, wrist):
    upper, fore = [rig.data.bones[n+'.'+side] for n in ('upper_arm','forearm')]
    shoulder=upper.head_local
    direction=(wrist-shoulder).normalized()
    dist=(wrist-shoulder).length
    along=(upper.length**2-fore.length**2+dist**2)/(2*dist)
    guide=Vector((1 if side=='L' else -1,.08,-.5))
    elbow=(shoulder+along*direction+(guide-direction*guide.dot(direction)).normalized()
           * math.sqrt(upper.length**2-along**2))
    for bone,a,b in ((upper,shoulder,elbow),(fore,elbow,wrist)):
        rigid(bone.name,a,(bone.tail_local-bone.head_local).rotation_difference(b-a).to_matrix())


# Both grips and the bundle share one rigid displacement. The elbows solve
# back to fixed shoulders as he lifts, checks his shopping, and settles again.
armature=santa.modifiers.get('Armature')
armature.show_viewport=False
for frame in range(1,scene.frame_end+1):
    scene.frame_set(frame)
    phase=math.tau*(frame-1)/(scene.frame_end-1)
    lift=(1-math.cos(phase))*.5
    delta=Vector((.016*lift,.012*lift,.082*lift))
    identity=Matrix.Identity(3)
    rigid('groceries',rig.data.bones['groceries'].head_local+delta,identity)
    animated=['groceries','head','eye.L','eye.R']
    for side,sign in [('L',1),('R',-1)]:
        wrist=Vector((sign*.322,-.415,1.125))+delta
        bend_arm(side,wrist)
        rigid('hand.'+side,wrist,identity)
        animated.extend(n+'.'+side for n in ('upper_arm','forearm','hand'))
    rig.pose.bones['head'].rotation_quaternion=(Quaternion((0,1,0),-.055-.12*lift)
        @ Quaternion((1,0,0),.045+.14*lift))
    for side in ('L','R'):
        rig.pose.bones['eye.'+side].rotation_quaternion=Quaternion((1,0,0),-.06-.11*lift)
    for name in animated:
        bone=rig.pose.bones[name]
        bone.keyframe_insert('rotation_quaternion',frame=frame,group=name)
        if name not in ('head','eye.L','eye.R'):
            bone.keyframe_insert('location',frame=frame,group=name)
armature.show_viewport=True
rig.animation_data.action.name='Santa02_Grocery_Lift'
scene.frame_set(1)
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
    for name,frame in [('front',1),('lift',61),('tote',1)]:
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
