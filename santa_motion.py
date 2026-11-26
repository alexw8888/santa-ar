"""Secondary motion shared by every Santa edition.

build_santa_base.py calls `ensure_secondary_rig` to add a few lightweight deformation bones (coat
hem, sleeves and hat tip) and reweight only the relevant garment vertices. Each edition's bake then
calls `sway` on every frame, before it solves the arms, to add a gentle, loopable body sway, cloth
follow-through and foot settling. These are ordinary skeletal keys, so they export to GLB / USDZ.

Blender 4.x / 5.x API; requires Blender's bundled bpy (not ordinary Python).
"""
import math

# Degrees; smaller is more believable. Feel free to adjust these four values.
BODY_TILT_DEG = 2.0
CLOTHING_SWAY_DEG = 3.0
FOOT_ADJUST_DEG = 1.0
HAT_FOLLOW_DEG = 3.0

SECONDARY_BONES = (
    'coat_hem', 'sleeve_sway.L', 'sleeve_sway.R', 'hat_tip',
)
BODY_BONES = ('hips', 'spine', 'chest')
FOOT_BONES = ('foot.L', 'foot.R')
ANIMATED_BONES = BODY_BONES + FOOT_BONES + SECONDARY_BONES


def _clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def ensure_secondary_rig(rig, character):
    """Idempotently install secondary bones and blend garment and beard weights.

    Runs once, on the base character. No simulated cloth/constraints required.
    """
    import bpy
    from mathutils import Vector

    if all(name in rig.data.bones for name in SECONDARY_BONES):
        return
    if any(name in rig.data.bones for name in SECONDARY_BONES):
        raise RuntimeError('Partially installed secondary rig: restore the original file and rerun.')

    # Give the coat and sleeves their own pivot points. Keep the hat tip a child
    # of head: it *always* follows the head and just adds a delayed wobble.
    specs = [('coat_hem', (0, 0, .74), (0, 0, .95), 'hips'),
             ('hat_tip', (-.310, .097, 1.966), (-.459, .164, 1.622), 'head')]
    for side in ('L', 'R'):
        a = rig.data.bones['forearm.' + side].head_local.copy()
        b = rig.data.bones['forearm.' + side].tail_local.copy()
        specs.append(('sleeve_sway.' + side, a.lerp(b, .56), a.lerp(b, .95),
                      'forearm.' + side))

    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    for name, head, tail, parent in specs:
        edit = rig.data.edit_bones.new(name)
        edit.head, edit.tail = head, tail
        edit.parent = rig.data.edit_bones[parent]
        edit.use_connect = False
        edit.use_deform = True
    bpy.ops.object.mode_set(mode='OBJECT')
    for name in SECONDARY_BONES:
        rig.pose.bones[name].rotation_mode = 'QUATERNION'

    groups = {name: character.vertex_groups.get(name) for name in
              list(SECONDARY_BONES) + list(BODY_BONES) +
              ['head', 'upper_arm.L', 'upper_arm.R', 'forearm.L', 'forearm.R',
               'thigh.L', 'thigh.R', 'shin.L', 'shin.R']}
    for name in SECONDARY_BONES:
        groups[name] = character.vertex_groups.new(name=name)

    # Material flags distinguish garments and hair from nearby skin and props.
    mesh = character.data
    flags = bytearray(len(mesh.vertices))
    materials = {'Crimson_velvet': 1, 'Scarlet_hat_velvet': 1, 'Ivory_plush_fur': 2, 'Silver_beard': 4}
    for poly in mesh.polygons:
        mat = mesh.materials[poly.material_index]
        mask = 8 if mat.name == 'Pompom fibers' else materials.get(mat.get('head_surface', mat.name), 0)
        if mask:
            for idx in poly.vertices:
                flags[idx] |= mask

    group_names = {vg.index: vg.name for vg in character.vertex_groups}
    counts = dict.fromkeys((*SECONDARY_BONES, 'chest'), 0)
    for vertex in mesh.vertices:
        flag = flags[vertex.index]
        if not flag:
            continue
        originals = [(group_names[g.group], g.weight) for g in vertex.groups]
        owners = {name for name, value in originals if value > .01}
        x, y, z = vertex.co
        target, influence = None, 0.0
        # The lower beard drapes over the chest as the upper beard follows a nod.
        if flag & 4 and owners == {'head'}:
            drape = _clamp((1.53 - z) / .18)
            influence = .94 * drape * drape * (3 - 2 * drape)
            target = 'chest'
        # The crown and pompom follow the flexible hat tip. The brim follows the head.
        elif owners == {'head'}:
            if flag & 1:
                along = _clamp((-x - .16) / .115)
                drop = _clamp((2.06 - z) / .27)
                influence = along * drop ** .65
            elif flag & 8:
                influence = 1.0
            target = 'hat_tip'
        # Coat material is bound to the three torso bones; leg fabric is bound
        # to thigh/shin bones and is consequently excluded automatically.
        elif (flag & 1 and owners and owners.issubset(set(BODY_BONES))
              and .68 < z < 1.04):
            influence = .63 * _clamp((1.04 - z) / .31) ** 1.5
            target = 'coat_hem'
        # The ring of white fur around the bottom of the coat is hips-bound.
        elif (flag & 2 and owners == {'hips'} and .65 < z < .81
              and abs(x) < .46 and abs(y) < .44):
            influence, target = .66, 'coat_hem'
        # Sleeve fabric and fur cuffs follow forearms, with a fraction of
        # extra motion near the wrist. Boots and gloves are never reweighted.
        elif flag & 3:
            for side in ('L', 'R'):
                allowed = {'upper_arm.' + side, 'forearm.' + side}
                if owners and owners.issubset(allowed):
                    bone = rig.data.bones['forearm.' + side]
                    axis = bone.tail_local - bone.head_local
                    t = _clamp((vertex.co - bone.head_local).dot(axis) /
                               axis.length_squared)
                    influence = .36 * _clamp((t - .28) / .67)
                    target = 'sleeve_sway.' + side
                    break
        if not target or influence < .018:
            continue
        # Renormalize all original groups so summed weights remain exactly 1.
        # This is important for the GLB/USDZ exporters and the existing tests.
        total = sum(w for _, w in originals)
        for name, weight in originals:
            character.vertex_groups[name].add([vertex.index],
                                               (1.0 - influence) * weight / total,
                                               'REPLACE')
        groups[target].add([vertex.index], influence, 'REPLACE')
        counts[target] += 1
    mesh.update()
    print('[secondary] deformation controls added:', counts, flush=True)
    rig['secondary_motion'] = 'coat / sleeves / hat tip; bone-based export-safe follow-through'


def sway(rig, t, activity=0.0):
    """Pose a lightweight loopable secondary layer at loop phase `t` (0..1); call before solving arms.

    `activity` ranges 0..1, indicating how far the main gesture has progressed.
    The shape is periodic and t = 0 and t = 1 are identical for looping AR.
    """
    from mathutils import Quaternion, Vector

    phase = 0.0 if t >= 1 else math.tau * t
    wave = math.sin(phase)
    counter = math.sin(2 * phase)
    # Delayed wiggle with its starting offset removed: exact loop closure.
    def lag(delay):
        return math.sin(phase - delay) - math.sin(-delay)
    gesture = _clamp(activity)

    def set_rotation(name, x=0.0, y=0.0, z=0.0):
        pb = rig.pose.bones[name]
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (
            Quaternion((1, 0, 0), math.radians(x)) @
            Quaternion((0, 1, 0), math.radians(y)) @
            Quaternion((0, 0, 1), math.radians(z))
        )

    # Small planted sway. Upper body responds more than hips so the feet do not
    # glide across the ground or the entire character pivot as one rigid block.
    b = BODY_TILT_DEG
    shift = .74 * wave + .22 * counter
    set_rotation('hips', x=.13*b*counter, z=.11*b*shift)
    set_rotation('spine', x=.24*b*(wave-.25*counter), z=.35*b*shift)
    set_rotation('chest', x=.16*b*wave, z=-.13*b*shift)

    # Coat hem and sleeves react a fraction of a beat after the torso/arms.
    c = CLOTHING_SWAY_DEG
    set_rotation('coat_hem', x=.34*c*lag(.24), z=.42*c*lag(.36))
    for side, direction in (('L', 1), ('R', -1)):
        set_rotation('sleeve_sway.'+side,
                     x=direction * .24*c*lag(.42),
                     z=direction * .30*c*(lag(.32) + .20*gesture*wave))

    # Head -> flexible crown -> pompom. The tip follows the parented head, but
    # overshoots/settles a little; no simulation cache is needed in AR.
    h = HAT_FOLLOW_DEG
    set_rotation('hat_tip', x=.36*h*lag(.29), z=.70*h*(lag(.40) + .12*gesture*wave))

    # Almost imperceptible boot angle and heel settling. Opposing phases make
    # weight transfer appear intentional while keeping both feet grounded.
    f = FOOT_ADJUST_DEG
    for side, direction in (('L', 1), ('R', -1)):
        set_rotation('foot.'+side, x=direction*.48*f*wave,
                     z=direction*.65*f*(wave-.22*counter))
        rig.pose.bones['foot.'+side].location = Vector((0, 0, .0025 * f *
                                    max(0.0, direction * wave)))
