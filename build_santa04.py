"""Build the Landmark on Robson edition from the shared Santa character.

blender -b --factory-startup --python-exit-code 1 -P build_santa04.py -- previews
The optional directory receives start, front, lift, tree and gift detail previews.
"""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
from mathutils import Quaternion, Vector  # noqa: E402

import santa_kit as kit  # noqa: E402
from santa_kit import (TAU, aim_eyes, ball, bound, cord, hold, look, material, place,  # noqa: E402
                       profile, rigid, rings, sheet, surface, textured, turn)

PIVOT = Vector((-.015, -.641, 1.075))
SPAN = .17
BOX_WIDTH, BOX_FRONT, BOX_BACK = .222, -.048, .185
BOX_BOTTOM, BOX_TOP = -.122, .119
LID_BOTTOM, LID_TOP, LID_OVERHANG = .107, .155, .008
WRAPPING = '641526'
TREE_SCALE = 1.22
FOLIAGE_BASE = .22
TREE = Vector((-.92, .70, FOLIAGE_BASE * TREE_SCALE))
HEIGHT, WIDTH, DEPTH = 1.60, .48, .86
CAMERA = Vector((-.25, -6.25, 1.99))
FRAMES = 193


def radius(z):
    return WIDTH * max(.02, 1 - z / HEIGHT) ** .92


light_wire = []
for k in range(271):
    t = k / 270
    z = .045 + (HEIGHT - .15) * t
    a = -math.pi / 2 + TAU * 5.2 * t
    r = radius(z) * 1.06 + .012
    light_wire.append(Vector((r * math.cos(a), r * DEPTH * math.sin(a), z - .019 * math.sin(a * 2))))
tree_lights = [(f'tree_light_{i:02}', p) for i, p in enumerate(light_wire[2::4], 1)]

kit.start(4, 'LandmarkOnRobson', 'photos/04 Landmark on Robson Santa.jpg', [
    ('gift', PIVOT, PIVOT + Vector((0, 0, .18)), 'root'),
] + [(name, TREE + p * TREE_SCALE, TREE + p * TREE_SCALE + Vector((0, 0, .025)), 'root')
     for name, p in tree_lights])
rig = kit.rig


def box_shell(bottom, top, overhang, mat):
    """Build a paper-covered box with flat faces and small rounded edges."""
    bevel = .006
    rows = []
    for z, inset in ((bottom, bevel), (bottom + bevel, 0), (top - bevel, 0), (top, bevel)):
        x = BOX_WIDTH + overhang
        front, back = BOX_FRONT - overhang, BOX_BACK + overhang
        row = []
        for cx, cy, angle in ((x - bevel, back - bevel, 0), (-x + bevel, back - bevel, math.pi / 2),
                              (-x + bevel, front + bevel, math.pi), (x - bevel, front + bevel, 3 * math.pi / 2)):
            for step in range(4):
                a = angle + step * math.pi / 6
                r = bevel - inset * .85
                row.append((cx + r * math.cos(a), cy + r * math.sin(a), z))
        rows.append(row)
    rings(rows, mat, rounded=False)


def logo_material():
    """Composite the supplied artwork onto the box color for opaque AR materials."""
    path = kit.ROOT / 'photos' / 'landmark-on-robson-logo.png'
    source = kit.bpy.data.images.load(str(path))
    width, height = source.size[:]
    texture_width = 1280
    texture_height = round(height * texture_width / width)
    aspect = width / height
    source.scale(texture_width, texture_height)
    pixels = np.empty(texture_width * texture_height * 4, dtype=np.float32)
    source.pixels.foreach_get(pixels)
    pixels = pixels.reshape(texture_height, texture_width, 4)
    alpha = pixels[:, :, 3:]
    rgb = kit.to_srgb(kit.from_srgb(pixels[:, :, :3]) * alpha + np.array(kit.linear(WRAPPING)) * (1 - alpha))
    kit.bpy.data.images.remove(source)

    mat = material('Landmark on Robson logo', WRAPPING, .48)
    nodes = mat.node_tree.nodes
    texture = nodes.new('ShaderNodeTexImage')
    texture.image = kit.image('Landmark_on_Robson_logo', rgb)
    texture.extension = 'EXTEND'
    mat.node_tree.links.new(texture.outputs['Color'], nodes['Principled BSDF'].inputs['Base Color'])
    return mat, aspect


box = material('Gift box sides', WRAPPING, .48)
lid = material('Gift box lid', '95243A', .43)
ribbon = material('Gift ribbon', 'DABE85', .32, metal=.36, sheen=.35)
logo, logo_aspect = logo_material()

with bound('gift'), place(*PIVOT):
    box_shell(BOX_BOTTOM, BOX_TOP, 0, box)
    box_shell(LID_BOTTOM, LID_TOP, LID_OVERHANG, lid)

    # The front face carries the original wordmark at its native aspect ratio.
    half_width = .175
    half_height = half_width / logo_aspect
    y, z = BOX_FRONT - .0004, .027
    surface([(-half_width, y, z - half_height), (half_width, y, z - half_height),
             (half_width, y, z + half_height), (-half_width, y, z + half_height)],
            [(0, 1, 2, 3)], logo, uv=[(0, 0), (1, 0), (1, 1), (0, 1)])

    # Two ribbon bands meet at the bow and wrap over the lid and down the sides.
    front, back = BOX_FRONT - LID_OVERHANG - .001, BOX_BACK + LID_OVERHANG + .001
    side = BOX_WIDTH + LID_OVERHANG + .001
    top, bottom = LID_TOP + .001, LID_BOTTOM
    wrap_y, strip = .07, .021
    around_x = [(-side, bottom), (-side, top - .006), (-side + .006, top),
                (side - .006, top), (side, top - .006), (side, bottom)]
    sheet([[(x, wrap_y + dy, z) for dy in (-strip, strip)] for x, z in around_x], ribbon, rounded=False)
    upper_band = top + .001
    around_y = [(front, bottom), (front, upper_band - .006), (front + .006, upper_band),
                (back - .006, upper_band), (back, upper_band - .006), (back, bottom)]
    sheet([[(x, y, z) for x in (-strip, strip)] for y, z in around_y], ribbon, rounded=False)
    for sign in (-1, 1):
        side_wrap = sign * (BOX_WIDTH + .001)
        sheet([[(side_wrap, wrap_y + dy, z) for dy in (-strip, strip)]
               for z in (BOX_BOTTOM + .007, LID_BOTTOM)], ribbon, rounded=False)
    sheet([[(x, BOX_BACK + .001, z) for x in (-strip, strip)] for z in (BOX_BOTTOM + .007, LID_BOTTOM)],
          ribbon, rounded=False)

    with place(0, wrap_y, LID_TOP):
        for sign in (-1, 1):
            loop = []
            for j in range(19):
                t = j / 18
                x = sign * (.011 + .116 * math.sin(math.pi * t))
                y = .030 * math.sin(TAU * t) + sign * .014 * math.sin(math.pi * t)
                z = .016 + .057 * math.sin(math.pi * t) ** 2 + .021 * math.sin(TAU * t)
                w = .008 + .014 * math.sin(math.pi * t) ** .6
                loop.append([(x, y + w * u, z + .008 * u * u) for u in (-1, 0, 1)])
            sheet(loop, ribbon)
            tail = []
            for j in range(9):
                t = j / 8
                tail.append([(sign * (.01 + .129 * t) + u * .019, -.095 * t + .012 * t**6 * (1 - abs(u)),
                              .006 + .020 * (1 - t)**3 + .010 * math.sin(math.pi * t) + .005 * u * u)
                             for u in (-1, 0, 1)])
            sheet(tail, ribbon)
        with place(0, 0, .023):
            profile([(-.018, .025, .019), (0, .027, .022), (.018, .020, .017)], ribbon, n=24)


# A tileable needle swatch adds short, dark strokes to the foliage.
rng = np.random.default_rng(4)
y, x = np.mgrid[:128, :128] / 128
needles = np.zeros((128, 128))
for _ in range(900):
    cx, cy = rng.uniform(0, 1, 2)
    a = rng.uniform(-.5, .5) + math.pi / 2 * rng.integers(0, 2)
    dx, dy = (x - cx + .5) % 1 - .5, (y - cy + .5) % 1 - .5
    along, across = dx * math.cos(a) + dy * math.sin(a), -dx * math.sin(a) + dy * math.cos(a)
    needles += np.exp(-(across / .006) ** 2) * (np.abs(along) < .05) * rng.uniform(.5, 1)
shade = np.clip(.55 + .35 * np.tanh(needles - .6), 0, 1)
fir = textured(material('Fir needles', '2F5E2A', .78, sheen=.25),
               shade[:, :, None] * np.array([.20, .40, .17]) + (1 - shade[:, :, None]) * np.array([.06, .16, .07]), .12)
fir_tips = material('Fresh fir tips', '4E8A3A', .7, sheen=.25)
bark = material('Spruce trunk', '5A3A22', .85)
planter = material('Tree planter', '805B39', .38, metal=.4)
red_bauble = material('Red glass bauble', 'C8102E', .16, coat=.85)
champagne_bauble = material('Champagne bauble', 'E3B968', .2, metal=.7, coat=.5)
gold = material('Tree ornament gold', 'D9A441', .27, metal=.65)
star_gold = material('Star topper', 'F4C36A', .29, metal=.56, emit=.25)
wire = material('Light wire', '1F3A1C', .6)
bulb_casing = material('Fairy light casings', '695842', .42)
bulb = material('Warm fairy lights', 'FFD27A', .3, emit=6)

rnd = random.Random(4)
with bound('root'), place(*TREE, scale=TREE_SCALE):
    profile([(-FOLIAGE_BASE, .139, .139), (-FOLIAGE_BASE + .014, .15, .15),
             (-.06, .173, .173), (-.047, .167, .167)], planter, n=36)
    profile([(-.075, .173, .173), (-.059, .176, .176), (-.049, .168, .168)], gold, n=36)
    profile([(-.051, .057, .057), (.07, .052, .052)], bark, n=12)
    tiers = 7
    for k in range(tiers):
        top = HEIGHT * (k + 1.25) / tiers if k < tiers - 1 else HEIGHT
        bottom = HEIGHT * (k - .15) / tiers if k else -.015
        rb, rt = radius(bottom) * 1.05, radius(top) * .55
        slope = rb * .78 + rt * .22
        phase = rnd.uniform(0, TAU)
        lobes = 13 - k
        profile([(bottom - .046, rb * .88, rb * .88 * DEPTH), (bottom, rb, rb * DEPTH),
                 (bottom + .25 * (top - bottom), slope, slope * DEPTH), (top, rt, rt * DEPTH)],
                fir, n=52, wobble=lambda a, z, p=phase, n=lobes:
                1 + .13 * math.cos(n * a + p) + .06 * math.cos(2.7 * n * a))
    for _ in range(1400):
        z = HEIGHT * rnd.random() ** 1.15 * .97
        a = rnd.uniform(0, TAU)
        r = radius(z) * rnd.uniform(.84, 1.03)
        base = Vector((r * math.cos(a), r * DEPTH * math.sin(a), z))
        out = Vector((math.cos(a), math.sin(a) / DEPTH * .8, -.35)).normalized() * rnd.uniform(.043, .078)
        cord([base - out * .3, base + out * .5, base + out], .006,
             fir_tips if rnd.random() < .36 else fir, [1, .7, .15], sides=4)

    cord(light_wire, .002, wire, sides=4)
    for name, p in tree_lights:
        ball(*p, .008, bulb_casing, 8, 4)
        with bound(name):
            ball(*p, .0125, bulb, 8, 4)
    for k in range(33):
        z = .085 + (HEIGHT - .27) * ((k * .618) % 1)
        a = rnd.uniform(0, TAU)
        r = radius(z) * 1.03 + .030
        c = Vector((r * math.cos(a), r * DEPTH * math.sin(a), z))
        size = rnd.uniform(.026, .037)
        ball(*c, size, red_bauble if k % 2 else champagne_bauble, 16, 8)
        with place(*c):
            profile([(size * .84, .007, .007), (size * 1.2, .006, .006)], gold, n=8)

    profile([(HEIGHT - .05, .014, .014), (HEIGHT + .118, .010, .010)], gold, n=12)
    with place(0, 0, HEIGHT + .124):
        rim = []
        for k in range(10):
            a = math.pi / 2 + TAU * k / 10
            r = .127 if k % 2 == 0 else .054
            rim.append((r * math.cos(a), 0, r * math.sin(a)))
        points = rim + [(0, -.037, 0), (0, .037, 0)]
        faces = [(10, i, (i + 1) % 10) for i in range(10)] + [(11, (i + 1) % 10, i) for i in range(10)]
        surface(points, faces, star_gold, closed=True)


# The eight-second loop lifts at the waist, offers at arm's length and retracts.
kit.santa_motion.BODY_TILT_DEG = 3.0
kit.santa_motion.CLOTHING_SWAY_DEG = 4.0
kit.santa_motion.FOOT_ADJUST_DEG = 1.25
kit.santa_motion.HAT_FOLLOW_DEG = 4.0


def ease(t, a, b):
    u = max(0.0, min(1.0, (t - a) / (b - a)))
    return u**3 * (10 + u * (-15 + 6 * u))


def pulse(t, a, b, c, d):
    return ease(t, a, b) * (1 - ease(t, c, d))


def phases(t):
    return pulse(t, .10, .36, .77, .96), pulse(t, .43, .59, .70, .81)


def clean_elbow_seams():
    """Remove only the detached decorative elbow rings from this edition's base mesh.

    The shared model creates each ring with 24 x 5 vertices. Match topology,
    red fabric, arm-only skin weights and the rest elbow position before deleting.
    """
    import bmesh
    obj = kit.santa
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
    print(f'[Santa04] Removed {count} detached elbow seam rings (expected 4).', flush=True)


def hold_gift(side, grip, rotation):
    """Santa04-only arm solution: relaxed, downward elbows; unchanged gift grip."""
    wrist = grip - rotation @ kit.GRIP[side]
    upper, fore = (rig.data.bones[n + '.' + side] for n in ('upper_arm', 'forearm'))
    shoulder = kit.attached(upper.name)
    delta = wrist - shoulder
    dist = delta.length
    if not abs(upper.length - fore.length) < dist < upper.length + fore.length - .005:
        raise ValueError(f'Gift wrist outside arm reach: {side}, {dist:.4f}')
    direction = delta / dist
    along = (upper.length**2 - fore.length**2 + dist**2) / (2 * dist)
    sign = 1 if side == 'L' else -1
    guide = Vector((.95 * sign, -.10, -0.92))
    pole = guide - direction * guide.dot(direction)
    if pole.length < 1e-6:
        guide = Vector((sign, 0, 0))
        pole = guide - direction * guide.dot(direction)
    elbow = shoulder + direction * along + pole.normalized() * math.sqrt(max(0, upper.length**2 - along**2))
    for bone, a, b in ((upper, shoulder, elbow), (fore, elbow, wrist)):
        rigid(bone.name, a, (bone.tail_local - bone.head_local).rotation_difference(b - a).to_matrix())
    rigid('hand.' + side, wrist, rotation)


def pose_at(t):
    lift, offer = phases(t)
    phase = 0. if t >= 1 else TAU * t
    wave, breathe = math.sin(phase), math.sin(2 * phase)
    # Anticipate the load, straighten as it rises, then relax on the return.
    prepare = pulse(t, .025, .10, .12, .25)
    settle = pulse(t, .78, .86, .93, .99)
    for name, degrees in (('spine', 3.0 + 3.0 * prepare - 4.0 * lift + 2.0 * offer + 1.2 * settle),
                          ('chest', 2.0 + 2.0 * prepare - 3.0 * lift + 1.5 * offer + .7 * breathe)):
        pb = rig.pose.bones[name]
        axis = pb.bone.matrix_local.to_3x3().inverted() @ Vector((1, 0, 0))
        pb.rotation_quaternion = pb.rotation_quaternion @ Quaternion(axis.normalized(), math.radians(degrees))
    kit.bpy.context.view_layer.update()

    # Clear upward arc, with a small dip before the lift and no inward pull.
    # A shared gift transform keeps both gloves attached throughout.
    centre = PIVOT + Vector((.014 * wave, -.012 * lift - .045 * offer,
                             -.025 * prepare + .225 * lift + .018 * offer + .005 * breathe))
    rotation = turn(1.8 * wave, 'Y') @ turn(3.0 + 2.0 * prepare - 6.0 * lift + 4.0 * offer, 'X')
    # Each glove pivots about its own grip, not about the gift's centre.
    # Keep the existing cupped gloves and front-corner contact points.
    grips = {'L': Vector((SPAN + .030, .010, -.014)), 'R': Vector((-(SPAN + .030), .010, -.014))}
    hand_rotations = {
        side: rotation @ turn(sign * (10 + 5 * lift + 3 * offer), 'Z')
        for side, sign in (('L', 1), ('R', -1))
    }

    # Project the gift's shared pivot into each arm's reach before posing the hands.
    constraints = []
    for side, grip in grips.items():
        upper = rig.data.bones['upper_arm.' + side]
        fore = rig.data.bones['forearm.' + side]
        offset = rotation @ grip - hand_rotations[side] @ kit.GRIP[side]
        constraints.append((kit.attached(upper.name) - offset, upper.length + fore.length - .025))
    for _ in range(100):
        for anchor, max_reach in constraints:
            delta = centre - anchor
            if delta.length > max_reach:
                centre = anchor + delta.normalized() * max_reach
        if all((centre - anchor).length <= max_reach + .00001 for anchor, max_reach in constraints):
            break
    else:
        raise RuntimeError('Gift grip reach constraints do not overlap')

    # Keep sleeve bones aligned with their forearms instead of adding cuff twist.
    for side in ('L', 'R'):
        sleeve = rig.pose.bones.get('sleeve_sway.' + side)
        if sleeve is not None:
            sleeve.rotation_quaternion = Quaternion((1, 0, 0, 0))
    rigid('gift', centre, rotation)
    for side, grip in grips.items():
        hold_gift(side, centre + rotation @ grip, hand_rotations[side])

    # Eyes lead the head back to the viewer just before the arms extend.
    gift_head = pulse(t, .04, .19, .30, .43) + .30 * pulse(t, .79, .87, .91, .99)
    gift_eyes = pulse(t, .02, .16, .28, .40) + .30 * pulse(t, .77, .85, .90, .98)
    neck = rig.pose.bones['neck']
    neck_deform = neck.matrix @ neck.bone.matrix_local.inverted()
    eye_origin = neck_deform @ kit.EYES
    bow = centre + rotation @ Vector((0, .06, LID_TOP + .045))
    gift_ray, viewer_ray = bow - eye_origin, CAMERA - eye_origin
    gift_direction, viewer_direction = gift_ray.normalized(), viewer_ray.normalized()
    head_direction = viewer_direction.lerp(gift_direction, gift_head)
    nod_share = .43 + .27 * lift
    look(kit.EYES + neck_deform.to_3x3().inverted() @ head_direction, turn_share=.82, nod_share=nod_share)
    eye_direction = viewer_direction.lerp(gift_direction, gift_eyes).normalized()
    eye_distance = viewer_ray.length * (1 - gift_eyes) + gift_ray.length * gift_eyes
    aim_eyes(eye_origin + eye_direction * eye_distance)

    # Each globe scales around its own center and disappears inside its casing when off.
    # The staggered groups also blink in AR formats that export skeletal animation only.
    for i, (name, _) in enumerate(tree_lights):
        blink = (5 * t + (i % 3) / 3) % 1
        size = .12 + .88 * pulse(blink, 0, .15, .53, .70)
        rig.pose.bones[name].scale = (size,) * 3


clean_elbow_seams()
kit.attach('Landmark on Robson props')
kit.bake('Santa04_Gift_Presentation', FRAMES, pose_at,
         ['gift', 'head', 'eye.L', 'eye.R'] +
         [f'{name}.{side}' for side in 'LR' for name in ('upper_arm', 'forearm', 'hand')] +
         [name for name, _ in tree_lights],
         activity=lambda t: max(phases(t)))
FRONT = (CAMERA, (-.38, .12, 1.14), 70, (800, 900))
kit.finish('santa04', FRONT, [
    ('start', 1, FRONT),
    ('lift', 70, FRONT),
    ('front', 112, FRONT),
    ('tree', 112, ((-2.25, -5.25, 1.70), (-.85, .47, 1.21), 70, (700, 850))),
    ('gift', 112, ((-.08, -2.48, 1.59), (-.02, -.63, 1.37), 84, (800, 550))),
])
