"""Build Santa 01: a detailed, mobile-friendly Santa pouring and sipping coffee.

blender -b --factory-startup --python-exit-code 1 -P build_santa01.py -- [preview_dir]
Writes santa01.blend, packed with its generated PBR textures. No hair particles,
external simulation, or runtime constraints are required by the AR exports.
"""
import bpy, bmesh, math, os, sys, random
import numpy as np
import zlib, struct
from mathutils import Vector, Matrix, Quaternion

HERE = os.path.dirname(os.path.abspath(__file__))
VERSION = 'santa01'
ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
PREVIEWS = ARGS[0] if ARGS else None
rng = random.Random(125)
TAU = math.tau
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for collection in (bpy.data.meshes, bpy.data.materials, bpy.data.armatures, bpy.data.actions):
    for item in list(collection):
        if item.users == 0:
            collection.remove(item)
scene = bpy.context.scene
scene.render.fps = 24
scene.frame_start, scene.frame_end = 1, 300

# -------------------- reproducible, image-based PBR materials (exportable to AR)
texture_dir = os.path.join(HERE, 'generated', VERSION)
os.makedirs(texture_dir, exist_ok=True)

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


def pbr_maps(name, color, kind, size=512):
    gen = np.random.default_rng(31 + len(name))
    y, x = np.mgrid[0:size, 0:size].astype(float) / size
    micro = gen.normal(0, 1, (size, size))
    if kind == 'cloth':
        weave = np.sin(x * TAU * 128) * np.sin(y * TAU * 128)
        height = .012 * micro + .025 * weave
        variation = .96 + .045 * micro + .025 * weave
        rough, metallic = .80, 0
    elif kind == 'fur':
        strands = np.sin(TAU * (x * 185 + .8 * np.sin(y * TAU * 3)))
        height = .024 * strands + .008 * micro
        variation = .94 + .035 * strands + .018 * micro
        rough, metallic = .84, 0
    elif kind == 'leather':
        pores = np.sin(x * TAU * 39 + np.sin(y * TAU * 31))
        height = .011 * micro + .009 * pores
        variation = .94 + .04 * micro + .035 * pores
        rough, metallic = .48, 0
    else:
        scratch = np.sin(y * TAU * 160 + np.sin(x * TAU * 2))
        height = .003 * micro + .003 * scratch
        variation = .95 + .024 * micro + .03 * np.sin(TAU*x*4)*np.sin(TAU*y*5)
        rough, metallic = .34, 1
    rgb = np.array(color)[None, None, :] * variation[:, :, None]
    # A tangent-space normal texture, rather than non-portable procedural nodes.
    dy, dx = np.gradient(height)
    normal = np.stack((-dx * 10, -dy * 10, np.ones_like(dx)), axis=-1)
    normal /= np.linalg.norm(normal, axis=-1)[:, :, None]
    orm = np.stack((np.ones_like(x), np.clip(rough + micro * .025, .05, 1), np.full_like(x, metallic)), axis=-1)
    return (image_file(name + '_color', rgb), image_file(name + '_normal', normal*.5+.5, 'Non-Color'),
            image_file(name + '_orm', orm, 'Non-Color'))

MATS = []
def material(name, color, rough=.5, metal=0, texture=None, alpha=1):
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
        color_im, normal_im, orm_im = pbr_maps(name, color, texture)
        nt = mat.node_tree
        def tex(im):
            node = nt.nodes.new('ShaderNodeTexImage'); node.image = im
            return node.outputs['Color']
        nt.links.new(tex(color_im), bs.inputs['Base Color'])
        normal = nt.nodes.new('ShaderNodeNormalMap')
        normal.inputs['Strength'].default_value = .20 if texture == 'fur' else .3
        nt.links.new(tex(normal_im), normal.inputs['Color'])
        nt.links.new(normal.outputs['Normal'], bs.inputs['Normal'])
        separate = nt.nodes.new('ShaderNodeSeparateColor')
        nt.links.new(tex(orm_im), separate.inputs['Color'])
        nt.links.new(separate.outputs['Green'], bs.inputs['Roughness'])
        nt.links.new(separate.outputs['Blue'], bs.inputs['Metallic'])
    MATS.append(mat)
    return mat.name

RED = material('Crimson_velvet', (.44, .012, .023), texture='cloth')
FUR = material('Ivory_fur', (.87, .84, .76), texture='fur')
HAIR = material('Silver_beard', (.91, .90, .85), texture='fur')
SKIN = material('Warm_skin', (.78, .44, .29), .58)
ROSY = material('Rosy_cheeks', (.69, .235, .18), .57)
LEATHER = material('Brown_leather', (.068, .030, .017), texture='leather')
SOLE = material('Dark_soles_and_belt', (.021, .013, .009), .6)
BRASS = material('Aged_brass', (.65, .39, .12), texture='brass')
GOLD = material('Polished_brass_edges', (.78, .51, .19), .25, .85)
WHITE = material('Eye_white_and_teeth', (.96, .925, .84), .3)
IRIS = material('Hazel_eyes', (.16, .065, .025), .3)
BLACK = material('Pupils', (.006, .003, .002), .2)
MOUTH = material('Mouth_interior', (.085, .010, .007), .8)
LIP = material('Warm_lips', (.48, .14, .11), .6)
COFFEE = material('Milky_coffee', (.43, .215, .078), .25)
GLASS = material('Clear_glass', (.45, .57, .62), .10, alpha=.14)
STITCH = material('Leather_stitching', (.25, .14, .065), .75)

# -------------------- skeleton and prop anchors
CUP = Vector((.15, -.48, 1.12))
KETTLE = Vector((-.44, -.40, 1.53))
SHOULDERS = {'L': Vector((.24, 0, 1.43)), 'R': Vector((-.24, 0, 1.43))}
UPPER, LOWER = .31, .30

def elbow_for(side, wrist):
    shoulder = SHOULDERS[side]
    direction = wrist - shoulder
    d = min(direction.length, UPPER + LOWER - .001)
    unit = direction.normalized()
    a = (UPPER*UPPER - LOWER*LOWER + d*d) / (2*d)
    guide = Vector((1 if side == 'L' else -1, .08, -.5))
    perp = (guide - unit*guide.dot(unit)).normalized()
    return shoulder + unit*a + perp*math.sqrt(max(0, UPPER*UPPER-a*a))

WRISTS = {'L': CUP + Vector((.16, .04, 0)), 'R': KETTLE + Vector((0, .08, .02))}
GRIPS = {'L': CUP + Vector((.10, 0, 0)), 'R': KETTLE + Vector((0, -.005, .015))}
BONES = [
 ('root',(0,0,0),(0,.15,0),None),
 ('hips',(0,0,.86),(0,0,1.05),'root'),
 ('spine',(0,0,1.05),(0,0,1.29),'hips'),
 ('chest',(0,0,1.29),(0,0,1.53),'spine'),
 ('neck',(0,0,1.53),(0,0,1.60),'chest'),
 ('head',(0,0,1.60),(0,0,1.86),'neck'),
 ('kettle',KETTLE,KETTLE+Vector((0,0,.12)),'root'),
 ('cup',CUP,CUP+Vector((0,0,.12)),'root'),
 ('liquid',CUP+Vector((0,0,-.075)),CUP+Vector((0,0,.025)),'cup'),
]
POUR_GRIP = Vector((-.18, -.49, 1.73))
POUR_ROT = Matrix.Rotation(math.radians(25), 3, 'Y')
SPOUT_LOCAL = Vector((.44, -.012, -.16))
STREAM_START = POUR_GRIP + POUR_ROT @ SPOUT_LOCAL
BONES.append(('stream', STREAM_START, STREAM_START+Vector((0,0,-.2)), 'root'))
for side, sign in (('L',1),('R',-1)):
    shoulder, elbow, wrist = SHOULDERS[side], elbow_for(side, WRISTS[side]), WRISTS[side]
    BONES += [(f'upper_arm.{side}',shoulder,elbow,'chest'),
              (f'forearm.{side}',elbow,wrist,f'upper_arm.{side}'),
              (f'hand.{side}',wrist,GRIPS[side],f'forearm.{side}'),
              (f'thigh.{side}',(sign*.14,0,.86),(sign*.15,0,.46),'hips'),
              (f'shin.{side}',(sign*.15,0,.46),(sign*.15,0,.12),f'thigh.{side}'),
              (f'foot.{side}',(sign*.15,0,.12),(sign*.15,-.17,.06),f'shin.{side}')]
SEG = {name:(Vector(h),Vector(t)) for name,h,t,parent in BONES}
GROUPS = {name:i for i,(name,*_) in enumerate(BONES)}
bm = bmesh.new()
DL = bm.verts.layers.deform.verify()
UV = bm.loops.layers.uv.verify()

# -------------------- geometry helpers with portable UVs and skin weights
def weights(p, names):
    if isinstance(names, str): return {names:1}
    values = {}
    for name in names:
        a,b = SEG[name]; ab=b-a
        t=max(0,min(1,(p-a).dot(ab)/ab.length_squared))
        values[name]=1/((p-a-t*ab).length**4+1e-8)
    total=sum(values.values())
    values={k:v/total for k,v in values.items() if v/total>.015}
    total=sum(values.values())
    return {k:v/total for k,v in values.items()}

def finish(vertices, mat, bones):
    index = next(i for i,m in enumerate(MATS) if m.name == mat)
    faces=set()
    for vertex in vertices:
        faces.update(vertex.link_faces)
        for name,w in weights(vertex.co,bones).items(): vertex[DL][GROUPS[name]]=w
    for face in faces:
        face.material_index=index; face.smooth=True

def ellipsoid(c, r, mat, bones='head', seg=24, rings=14, direction=None, euler=None, fuzz=0):
    rot=Matrix.Identity(3)
    if direction is not None: rot=Vector(direction).to_track_quat('Z','Y').to_matrix()
    if euler is not None:
        from mathutils import Euler
        rot=Euler(tuple(math.radians(v) for v in euler)).to_matrix()
    transform=Matrix.Translation(c) @ rot.to_4x4() @ Matrix.Diagonal((*r,1))
    verts=bmesh.ops.create_uvsphere(bm,u_segments=seg,v_segments=rings,radius=1,matrix=transform,calc_uvs=True)['verts']
    if fuzz:
        for v in verts:
            normal=(v.co-Vector(c)).normalized()
            v.co+=normal*rng.uniform(-fuzz,fuzz)
    finish(verts,mat,bones)

def uv_face(verts, coords):
    f=bm.faces.new(verts)
    for loop,uv in zip(f.loops,coords): loop[UV].uv=uv
    return f

def tube(points,radii,mat,bones='head',sides=10,sub=2,cap=True,noise=0):
    pts=[Vector(p) for p in points]; P=[]; R=[]
    for i in range(len(pts)-1):
        for j in range(sub):
            t=j/sub; P.append(pts[i].lerp(pts[i+1],t)); R.append(radii[i]*(1-t)+radii[i+1]*t)
    P.append(pts[-1]); R.append(radii[-1])
    rings=[]; lengths=[0]
    n=None
    for i,(p,r) in enumerate(zip(P,R)):
        tangent=(P[min(i+1,len(P)-1)]-P[max(i-1,0)]).normalized()
        if n is None:
            n=tangent.cross(Vector((0,0,1)) if abs(tangent.z)<.95 else Vector((1,0,0))).normalized()
        n=(n-tangent*n.dot(tangent)).normalized(); b=tangent.cross(n)
        ring=[]
        for j in range(sides):
            a=TAU*j/sides; rr=r*(1+rng.uniform(-noise,noise))
            ring.append(bm.verts.new(p+(math.cos(a)*n+math.sin(a)*b)*rr))
        rings.append(ring)
        if i: lengths.append(lengths[-1]+(P[i]-P[i-1]).length)
    total=max(lengths[-1],1e-5)
    for i,(a,b) in enumerate(zip(rings,rings[1:])):
        for j in range(sides):
            uv_face((a[j],a[(j+1)%sides],b[(j+1)%sides],b[j]),
                    ((j/sides,lengths[i]/total),((j+1)/sides,lengths[i]/total),((j+1)/sides,lengths[i+1]/total),(j/sides,lengths[i+1]/total)))
    if cap:
        bm.faces.new(tuple(reversed(rings[0]))); bm.faces.new(tuple(rings[-1]))
    finish([v for ring in rings for v in ring],mat,bones)

def torus(c, normal, major, minor, mat,bones='head',depth=None, sides=48, cross=8, fuzz=0):
    c=Vector(c); rot=Vector(normal).to_track_quat('Z','Y').to_matrix()
    rings=[]
    for i in range(sides):
        a=TAU*i/sides; center=Vector((major*math.cos(a),(depth or major)*math.sin(a),0))
        radial=Vector((math.cos(a),math.sin(a),0))
        ring=[]
        for j in range(cross):
            v=TAU*j/cross; r=minor+rng.uniform(-fuzz,fuzz)
            ring.append(bm.verts.new(c+rot@(center+r*(radial*math.cos(v)+Vector((0,0,math.sin(v)))))))
        rings.append(ring)
    for i in range(sides):
        for j in range(cross):
            uv_face((rings[i][j],rings[(i+1)%sides][j],rings[(i+1)%sides][(j+1)%cross],rings[i][(j+1)%cross]),
                    ((i/sides,j/cross),((i+1)/sides,j/cross),((i+1)/sides,(j+1)/cross),(i/sides,(j+1)/cross)))
    finish([v for ring in rings for v in ring],mat,bones)

def lathe(c, profile, mat,bones, sides=48,ellipse=1,flute=0):
    # profile = (height, radius), optionally with a front/back center offset.
    c=Vector(c); rings=[]
    for i,row in enumerate(profile):
        z,r=row[:2]; offset=row[2] if len(row)>2 else 0
        ring=[]
        for j in range(sides):
            a=TAU*j/sides; rr=r+flute*math.cos(16*a)
            ring.append(bm.verts.new(c+Vector((rr*math.cos(a),rr*ellipse*math.sin(a)+offset,z))))
        rings.append(ring)
    for i in range(len(rings)-1):
        for j in range(sides):
            uv_face((rings[i][j],rings[i][(j+1)%sides],rings[i+1][(j+1)%sides],rings[i+1][j]),
                    ((j/sides,i/(len(rings)-1)),((j+1)/sides,i/(len(rings)-1)),((j+1)/sides,(i+1)/(len(rings)-1)),(j/sides,(i+1)/(len(rings)-1))))
    bm.faces.new(tuple(reversed(rings[0]))); bm.faces.new(tuple(rings[-1]))
    finish([v for ring in rings for v in ring],mat,bones)

def fur_ring(c,normal,major,minor,bones,depth=None,tufts=70):
    torus(c,normal,major,minor,FUR,bones,depth=depth,sides=64,cross=12,fuzz=.0025)
    rot=Vector(normal).to_track_quat('Z','Y').to_matrix(); c=Vector(c)
    for i in range(tufts):
        a=rng.uniform(0,TAU); v=rng.uniform(0,TAU)
        center=Vector((major*math.cos(a),(depth or major)*math.sin(a),0))
        radial=Vector((math.cos(a),math.sin(a),0))
        n=radial*math.cos(v)+Vector((0,0,math.sin(v)))
        p=c+rot@(center+minor*n)
        drift=rot@Vector((-.004*math.sin(a),.004*math.cos(a),-.012))
        if i % 2 == 0:
            ellipsoid(p+rot@n*.002, (.008,.008,.010), FUR, bones,
                      seg=10, rings=6, direction=rot@n)
        else:
            tube([p,p+rot@n*.004+drift*.18,p+rot@n*.006+drift*.3],
                 [.0035,.0025,.0006],FUR,bones,sides=5,sub=1)

# -------------------- coat, trousers, belt and boots
BODY=['hips','spine','chest']
lathe((0,0,0),[(.69,.28,-.01),(.72,.31,-.01),(.79,.30,-.015),(.91,.325,-.015),
      (1.04,.355,-.025),(1.16,.35,-.015),(1.30,.31,0),(1.40,.275,.015),(1.48,.20,.01),(1.53,.105,0)],
      RED,BODY,sides=64,ellipse=.82)
fur_ring((0,-.01,.72),(0,0,1),.30,.056,['hips'],depth=.245,tufts=110)
# The fur opening follows the coat front rather than floating in front of it.
tube([(0,-.257,.76),(0,-.278,.90),(0,-.302,1.06),(0,-.283,1.22),(0,-.236,1.38),(0,-.14,1.50)],
     [.035,.033,.034,.033,.035,.035],FUR,BODY,sides=14,sub=4,noise=.08)
fur_ring((0,0,1.51),(0,0,1),.11,.031,['chest','neck'],depth=.09,tufts=35)
torus((0,-.018,.975),(0,0,1),.329,.032,SOLE,['hips','spine'],depth=.27,sides=64,cross=10)
# Rounded rectangular buckle, tongue, pin and small belt holes.
buckle=[(-.064,-.329,.928),(.064,-.329,.928),(.077,-.329,.941),(.077,-.329,1.018),(.064,-.329,1.03),
        (-.064,-.329,1.03),(-.077,-.329,1.018),(-.077,-.329,.941),(-.064,-.329,.928)]
tube(buckle,[.011]*len(buckle),BRASS,['hips','spine'],sides=8,sub=2)
tube([(-.068,-.342,.979),(.026,-.342,.979)],[.0045,.003],GOLD,['hips','spine'],sides=8)
for x in (.115,.15,.185): ellipsoid((x,-.294,.976),(.004,.003,.004),BLACK,['hips','spine'],seg=10,rings=6)
for sign,side in ((1,'L'),(-1,'R')):
    x=sign*.15
    tube([(x,0,.84),(x,.0,.67),(x,.012,.47),(x,0,.30)],[.13,.125,.108,.095],RED,
         ['hips',f'thigh.{side}',f'shin.{side}'],sides=24,sub=4,noise=.015)
    fur_ring((x,0,.305),(0,0,1),.104,.046,f'shin.{side}',tufts=50)
    ellipsoid((x,.01,.17),(.10,.105,.16),LEATHER,f'foot.{side}',seg=28,rings=18)
    ellipsoid((x,-.105,.079),(.12,.205,.074),SOLE,f'foot.{side}',seg=32,rings=14)
    ellipsoid((x,-.105,.108),(.115,.195,.086),LEATHER,f'foot.{side}',seg=32,rings=18)
    # Toe seam and little stitch marks along the welt.
    seam=[]
    for j in range(20):
        a=math.pi+j*math.pi/19
        seam.append((x+.108*math.cos(a),-.10+.181*math.sin(a),.081))
    tube(seam,[.0025]*len(seam),STITCH,f'foot.{side}',sides=5,sub=1)
    for j in range(18):
        a=math.pi+j*math.pi/17
        p=Vector((x+.112*math.cos(a),-.10+.189*math.sin(a),.065))
        tube([p,p+Vector((0,0,.007))],[.0012,.0012],STITCH,f'foot.{side}',sides=4,sub=1)
    # Ankle strap and brass boot buckle.
    torus((x,.008,.20),(0,0,1),.102,.012,SOLE,f'foot.{side}',depth=.105,sides=32,cross=6)
    p=[(x-.031,-.103,.173),(x+.031,-.103,.173),(x+.031,-.103,.221),(x-.031,-.103,.221),(x-.031,-.103,.173)]
    tube(p,[.004]*5,GOLD,f'foot.{side}',sides=6,sub=1)

# -------------------- face, beard, glasses, brows and drooping cap
ellipsoid((0,.012,1.727),(.177,.153,.188),SKIN,seg=48,rings=32)
for sign in (-1,1):
    ellipsoid((sign*.17,.012,1.735),(.033,.027,.052),SKIN,seg=20,rings=14)
    ellipsoid((sign*.183,-.010,1.734),(.016,.012,.031),ROSY,seg=16,rings=10)
    ellipsoid((sign*.108,-.114,1.716),(.056,.028,.035),ROSY,seg=24,rings=14)
    ellipsoid((sign*.068,-.119,1.790),(.037,.023,.038),WHITE,seg=28,rings=18)
    ellipsoid((sign*.061,-.141,1.791),(.017,.009,.022),IRIS,seg=24,rings=14)
    ellipsoid((sign*.061,-.149,1.792),(.009,.005,.014),BLACK,seg=20,rings=12)
    ellipsoid((sign*.061-.006,-.153,1.803),(.005,.003,.006),WHITE,seg=12,rings=8)
    # Lower eyelid and smiling eye creases.
    tube([(sign*.035,-.128,1.774),(sign*.067,-.139,1.756),(sign*.100,-.12,1.770)],
         [.004,.005,.003],SKIN,sides=8,sub=3)
    tube([(sign*.027,-.106,1.841),(sign*.055,-.122,1.852),(sign*.082,-.119,1.847),(sign*.106,-.1,1.833)],
         [.008,.014,.013,.003],HAIR,sides=9,sub=3)
    # Round wire spectacles, open lenses to avoid overlapping transparent surfaces.
    torus((sign*.069,-.153,1.787),(0,1,0),.047,.0022,GOLD,sides=48,cross=6,depth=.039)
    tube([(sign*.115,-.147,1.792),(sign*.169,-.08,1.798),(sign*.179,.01,1.783)],
         [.0022]*3,GOLD,sides=6,sub=3)
tube([(-.024,-.157,1.797),(0,-.168,1.803),(.024,-.157,1.797)],[.0022]*3,GOLD,sides=6,sub=3)
ellipsoid((0,-.153,1.731),(.048,.041,.040),ROSY,seg=32,rings=20)
ellipsoid((0,-.159,1.649),(.065,.025,.047),LIP,seg=32,rings=18)
ellipsoid((0,-.178,1.651),(.054,.012,.035),MOUTH,seg=32,rings=18)
ellipsoid((0,-.187,1.628),(.033,.004,.009),LIP,seg=20,rings=10)
ellipsoid((0,-.189,1.672),(.033,.004,.008),WHITE,seg=20,rings=10)
# A shaped beard underlay with layered wavy locks following its silhouette.
lathe((0,0,0),[(1.27,.012,-.295),(1.30,.055,-.27),(1.37,.12,-.23),(1.47,.18,-.15),
      (1.57,.207,-.075),(1.65,.203,.0),(1.70,.17,.028)],HAIR,'head',sides=48,ellipse=.73)
beard_z = [1.27,1.30,1.37,1.47,1.57,1.65,1.70]
beard_w = [.012,.055,.12,.18,.207,.203,.17]
beard_y = [-.295,-.27,-.23,-.15,-.075,0,.028]
for i in range(165):
    side = rng.uniform(-.97,.97)
    startz = rng.uniform(1.50,1.70)
    endz = max(1.278,startz-rng.uniform(.15,.35))
    points=[]
    for j in range(10):
        u=j/9
        z=startz+(endz-startz)*u
        width=float(np.interp(z,beard_z,beard_w))
        center_y=float(np.interp(z,beard_z,beard_y))
        x=side*width+.006*math.sin(u*TAU*1.4+i)*math.sin(u*math.pi)
        y=center_y-width*.73*math.sqrt(max(.03,1-(x/max(width,.001))**2))-.004
        y-=.003*math.sin(u*TAU*1.6+i)
        points.append((x,y,z))
    radius=rng.uniform(.005,.010)
    tube(points,[radius*.5,radius,radius,radius*.95,radius*.9,radius*.8,
                 radius*.7,radius*.5,radius*.3,.0007],HAIR,sides=7,sub=1)
# Swept, curling moustache with individual clumps, free of the open mouth.
for sign in (-1,1):
    for i in range(9):
        z=1.694+(i-4)*.0018
        tube([(sign*.012,-.177,z),(sign*.048,-.194,z-.011),(sign*.092,-.177,z-.008),
              (sign*.132,-.143,z+.018),(sign*.14,-.122,z+.034)],
             [.006,.011,.009,.004,.0007],HAIR,sides=7,sub=2)
    # Hair at the temples and behind the ears.
    ellipsoid((sign*.151,.036,1.732),(.041,.105,.10),HAIR,seg=20,rings=14)
# Cap crown and droop; the pompom is supported by geometry rather than particles.
tube([(0,.018,1.86),(0,.045,1.99),(.055,.07,2.075),(.145,.065,2.087),(.235,.055,2.035),(.28,.035,1.936)],
     [.175,.15,.105,.075,.045,.016],RED,'head',sides=32,sub=4)
fur_ring((0,.012,1.875),(0,0,1),.174,.049,'head',depth=.15,tufts=110)
ellipsoid((.28,.035,1.908),(.065,.061,.067),FUR,seg=24,rings=16,fuzz=.004)
for i in range(60):
    n=Vector((rng.uniform(-1,1),rng.uniform(-1,1),rng.uniform(-1,1))).normalized()
    p=Vector((.28,.035,1.908))+n*.058
    tube([p,p+n*.016+Vector((0,0,-.005))],[.004,.0005],FUR,sides=5,sub=2)

# -------------------- arms, tailored sleeves and sculpted gripping gloves
for side in ('L','R'):
    shoulder,elbow,wrist = SHOULDERS[side],elbow_for(side,WRISTS[side]),WRISTS[side]
    upper=f'upper_arm.{side}'; fore=f'forearm.{side}'; hand=f'hand.{side}'
    # Smooth bulging sleeves ending just behind the wrist.
    direction=(wrist-elbow).normalized()
    cuff=wrist-direction*.035
    tube([shoulder+(elbow-shoulder)*-.12,shoulder.lerp(elbow,.28),elbow,
          elbow.lerp(cuff,.55),cuff],[.108,.125,.108,.096,.088],RED,[upper,fore],sides=24,sub=3)
    fur_ring(cuff,direction,.086,.041,fore,tufts=60)
    # A few shallow folds reinforce the elbow silhouette without expensive cloth simulation.
    for offset in (-.025,.015):
        center=elbow+direction*offset
        torus(center,direction,.103,.006,RED,[upper,fore],sides=24,cross=5)
    if side=='R':
        ellipsoid(KETTLE+Vector((0,.022,.035)),(.079,.052,.050),LEATHER,hand,seg=24,rings=16)
        for i in range(4):
            x=(i-1.5)*.031
            points=[KETTLE+Vector((x,-.002,.060)),KETTLE+Vector((x,-.038,.044)),
                    KETTLE+Vector((x,-.045,.008)),KETTLE+Vector((x,-.023,-.014))]
            tube(points,[.018,.018,.015,.010],LEATHER,hand,sides=10,sub=3)
            tube([points[1]+Vector((-.009,-.002,0)),points[1]+Vector((.009,-.002,0))],
                 [.0015,.0015],STITCH,hand,sides=4,sub=1)
        tube([KETTLE+Vector((.078,.012,.035)),KETTLE+Vector((.068,-.023,.005)),KETTLE+Vector((.036,-.038,-.011))],
             [.023,.022,.012],LEATHER,hand,sides=10,sub=3)
    else:
        ellipsoid(CUP+Vector((.107,.007,-.005)),(.057,.052,.068),LEATHER,hand,seg=24,rings=16)
        for i in range(4):
            z=.049-i*.029
            points=[CUP+Vector((.109,-.02,z)),CUP+Vector((.076,-.062,z)),
                    CUP+Vector((.028,-.069,z-.003)),CUP+Vector((.009,-.053,z-.008))]
            tube(points,[.016,.017,.014,.008],LEATHER,hand,sides=10,sub=3)
        tube([CUP+Vector((.103,.026,.043)),CUP+Vector((.057,.049,.063)),CUP+Vector((.025,.044,.047))],
             [.022,.020,.012],LEATHER,hand,sides=10,sub=3)

# -------------------- engraved brass kettle, curved spout and wood handle
body=KETTLE+Vector((0,0,-.31))
lathe(body,[(-.14,.105),(-.13,.14),(-.105,.164),(.07,.17),(.105,.155),(.12,.125),(.125,.10)],
      BRASS,'kettle',sides=48)
for z,r in ((-.12,.149),(.089,.162),(.124,.105)):
    torus(body+Vector((0,0,z)),(0,0,1),r,.0055,GOLD,'kettle',sides=48,cross=6)
lathe(body,[(.125,.12),(.137,.11),(.156,.072),(.163,.025)],GOLD,'kettle',sides=40)
ellipsoid(body+Vector((0,0,.177)),(.026,.026,.022),BRASS,'kettle',seg=20,rings=12)
spout=[body+Vector((.135,0,-.04)),body+Vector((.215,-.004,-.015)),body+Vector((.253,-.008,.06)),
       body+Vector((.326,-.012,.13)),KETTLE+SPOUT_LOCAL]
tube(spout,[.038,.031,.024,.018,.015],BRASS,'kettle',sides=16,sub=4,cap=False)
torus(KETTLE+SPOUT_LOCAL,spout[-1]-spout[-2],.015,.0035,GOLD,'kettle',sides=24,cross=6)
ellipsoid(KETTLE+SPOUT_LOCAL-(spout[-1]-spout[-2]).normalized()*.006,(.012,.012,.004),MOUTH,'kettle',seg=16,rings=8,
          direction=spout[-1]-spout[-2])
# Bail handle with a dark wooden grip at the apex.
arc=[KETTLE+Vector((.163*math.cos(a),0,-.18+.18*math.sin(a))) for a in [math.pi*i/24 for i in range(25)]]
tube(arc,[.009]*25,GOLD,'kettle',sides=8,sub=1)
grip=[KETTLE+Vector((.16*math.cos(a),0,-.18+.18*math.sin(a))) for a in [math.pi*.30+math.pi*.40*i/16 for i in range(17)]]
tube(grip,[.015]*17,LEATHER,'kettle',sides=10,sub=1)
for sign in (-1,1):
    ellipsoid(KETTLE+Vector((sign*.16,0,-.18)),(.014,.017,.020),GOLD,'kettle',seg=16,rings=10)
# Thin embossed ornamental bands read at close range without a texture-dependent logo.
for z in (-.085,.052):
    for k in range(12):
        a=math.pi+math.pi*k/11
        c=body+Vector((.166*math.cos(a),.166*math.sin(a),z))
        tangent=Vector((-math.sin(a),math.cos(a),0))
        points=[c+tangent*(j-.5)*.018+Vector((0,0,.006*math.sin(j*TAU))) for j in (0,.25,.5,.75,1)]
        tube(points,[.0012]*5,GOLD,'kettle',sides=4,sub=1)
# A simple coffee bean medallion on the front of the kettle.
ellipsoid(body+Vector((0,-.169,-.015)),(.033,.004,.044),LEATHER,'kettle',seg=24,rings=14,euler=(0,0,-20))
tube([body+Vector((-.006,-.174,.020)),body+Vector((.006,-.175,-.013)),body+Vector((-.004,-.174,-.046))],
     [.0018]*3,GOLD,'kettle',sides=5,sub=3)

# -------------------- ribbed glass, moving coffee level and timed liquid stream
profile=[(-.09,.045),(-.085,.05),(.078,.066),(.09,.066),(.09,.062),(.078,.062),(-.078,.047),(-.08,.006)]
lathe(CUP,profile,GLASS,'cup',sides=48,flute=.0015)
torus(CUP+Vector((0,0,.089)),(0,0,1),.064,.0028,GLASS,'cup',sides=48,cross=8)
torus(CUP+Vector((0,0,-.085)),(0,0,1),.047,.004,GLASS,'cup',sides=40,cross=6)
lathe(CUP, [(-.075,.044),(.049,.059),(.052,.058)],COFFEE,'liquid',sides=48,flute=.0004)
# The stream is a skinned mesh, animated with a dedicated bone so it also exports to USDZ.
end=CUP+Vector((0,0,.048))
tube([STREAM_START,STREAM_START+Vector((.001,.002,-.065)),end+Vector((.001,0,.045)),end],
     [.0065,.0075,.007,.006],COFFEE,'stream',sides=9,sub=4)
torus(end,(0,0,1),.018,.0024,COFFEE,'stream',sides=24,cross=5)

# -------------------- object and skin creation
for vertex in bm.verts:
    if vertex[DL].get(GROUPS['head'], 0) > .99:
        vertex.co.x *= 1.10
        vertex.co.y *= 1.06
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
mesh=bpy.data.meshes.new('Santa01_Mesh'); bm.to_mesh(mesh); bm.free()
mesh.update(); mesh.calc_loop_triangles()
character=bpy.data.objects.new('Santa01',mesh); scene.collection.objects.link(character)
for mat in MATS: mesh.materials.append(mat)
for name in GROUPS: character.vertex_groups.new(name=name)
arm=bpy.data.armatures.new('Santa01_Rig')
rig=bpy.data.objects.new('Santa01_Rig',arm); scene.collection.objects.link(rig)
bpy.context.view_layer.objects.active=rig; rig.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
for name,h,t,parent in BONES:
    bone=arm.edit_bones.new(name); bone.head=h; bone.tail=t
    if parent: bone.parent=arm.edit_bones[parent]
bpy.ops.object.mode_set(mode='OBJECT')
character.parent=rig
mod=character.modifiers.new('Armature','ARMATURE'); mod.object=rig
for pb in rig.pose.bones: pb.rotation_mode='QUATERNION'
assert all(v.groups and abs(sum(g.weight for g in v.groups)-1)<1e-4 for v in mesh.vertices)
print(f'[model] {len(mesh.vertices):,} vertices, {len(mesh.loop_triangles):,} triangles, {len(MATS)} materials',flush=True)

# -------------------- bake the hand/prop choreography into ordinary bone keys
def smooth(t): return max(0,min(1,t))**2*(3-2*max(0,min(1,t)))
def ramp(f,a,b): return smooth((f-a)/(b-a))
def rigid_pose(name,new_head,rotation):
    bone=rig.data.bones[name]
    pose=rig.pose.bones[name]
    rest_head=bone.head_local
    pose.matrix=Matrix.Translation(new_head) @ rotation.to_4x4() @ Matrix.Translation(-rest_head) @ bone.matrix_local
    bpy.context.view_layer.update()

def orient_segment(name,start,end):
    a,b=SEG[name]
    rotation=(b-a).rotation_difference(end-start).to_matrix()
    rigid_pose(name,start,rotation)

mod.show_viewport=False
for frame in range(1,301):
    scene.frame_set(frame)
    # Approach -> pour -> lower kettle -> raise glass -> sip -> return.
    kettle_amount=ramp(frame,24,60)*(1-ramp(frame,132,168))
    cup_amount=ramp(frame,168,204)*(1-ramp(frame,240,276))
    kpos=KETTLE.lerp(POUR_GRIP,kettle_amount)
    krot=Matrix.Rotation(math.radians(25)*kettle_amount,3,'Y')
    cpos=CUP.lerp(Vector((.015,-.286,1.58)),cup_amount)
    crot=Matrix.Rotation(math.radians(-23)*cup_amount,3,'X')
    rigid_pose('kettle',kpos,krot)
    rigid_pose('cup',cpos,crot)
    for side,pos,rot,origin in (('R',kpos,krot,KETTLE),('L',cpos,crot,CUP)):
        wrist=pos+rot@(WRISTS[side]-origin)
        grip=pos+rot@(GRIPS[side]-origin)
        elbow=elbow_for(side,wrist)
        orient_segment(f'upper_arm.{side}',SHOULDERS[side],elbow)
        orient_segment(f'forearm.{side}',elbow,wrist)
        rigid_pose(f'hand.{side}',wrist,rot)
    head=rig.pose.bones['head']
    head.rotation_quaternion=Quaternion((1,0,0), math.radians(4)*kettle_amount-math.radians(4)*cup_amount)
    flow=ramp(frame,62,66)*(1-ramp(frame,125,129))
    level=.42+.58*ramp(frame,66,125)-.58*ramp(frame,211,239)
    # The stream follows the rising coffee surface during the pour.
    surface=CUP.z-.075+.127*level
    length=(STREAM_START.z-surface)/(STREAM_START.z-end.z)
    rig.pose.bones['stream'].scale=(max(.01,flow),max(.01,flow*length),max(.01,flow))
    rig.pose.bones['liquid'].scale=(1,level,1)
    for name in ['kettle','cup','upper_arm.L','forearm.L','hand.L','upper_arm.R','forearm.R','hand.R','head','stream','liquid']:
        pb=rig.pose.bones[name]
        pb.keyframe_insert('location',frame=frame)
        pb.keyframe_insert('rotation_quaternion',frame=frame)
        pb.keyframe_insert('scale',frame=frame)
mod.show_viewport=True
rig.animation_data.action.name='Santa01_Pour_and_Drink'
for fc in rig.animation_data.action.fcurves:
    for k in fc.keyframe_points: k.interpolation='LINEAR'
rig.animation_data.action.use_fake_user=True
scene.frame_set(1)

# -------------------- studio for editable scene and presentation renders
world=bpy.data.worlds.new('Studio_world'); world.use_nodes=True
world.node_tree.nodes['Background'].inputs['Color'].default_value=(.28,.32,.40,1)
world.node_tree.nodes['Background'].inputs['Strength'].default_value=.25
scene.world=world

def area(name,position,power,color,size):
    data=bpy.data.lights.new(name,'AREA'); data.energy=power; data.color=color; data.shape='DISK'; data.size=size
    ob=bpy.data.objects.new(name,data); scene.collection.objects.link(ob); ob.location=position
    ob.rotation_euler=(Vector((0,0,1.1))-ob.location).to_track_quat('-Z','Y').to_euler()
area('Key_softbox',(-3,-4,5),400,(1,.83,.68),4)
area('Fill_softbox',(3,-2,3),200,(.75,.86,1),3)
area('Rim_softbox',(1,3,4),500,(1,.78,.56),3)
cam=bpy.data.objects.new('Camera',bpy.data.cameras.new('Camera')); scene.collection.objects.link(cam)
cam.location=(2.15,-6.3,2.75); cam.data.lens=82
cam.rotation_euler=(Vector((-.035,-.12,1.05))-cam.location).to_track_quat('-Z','Y').to_euler()
scene.camera=cam
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,.002))
floor=bpy.context.object; floor.name='Preview_ground'
floor.is_shadow_catcher=True
scene.render.engine='CYCLES'; scene.cycles.samples=32; scene.cycles.use_denoising=True
scene.cycles.max_bounces=6; scene.cycles.transparent_max_bounces=6
scene.render.resolution_x,scene.render.resolution_y=800,1000
scene.render.resolution_percentage=100
scene.render.film_transparent=True
scene.view_settings.view_transform='AgX'
scene.view_settings.look='AgX - Medium High Contrast'
scene.view_settings.exposure=-.3
for ob in scene.objects: ob.select_set(False)
rig.select_set(True); bpy.context.view_layer.objects.active=rig
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE,VERSION+'.blend'),compress=True)
print('[model] Saved packed Blender scene',flush=True)
if PREVIEWS:
    os.makedirs(PREVIEWS,exist_ok=True)
    for name,frame in [('ready',1),('pour',92),('drink',222)]:
        scene.frame_set(frame)
        scene.render.filepath=os.path.join(PREVIEWS,VERSION+'-'+name+'.png')
        bpy.ops.render.render(write_still=True)
        print('[render] '+name,flush=True)
