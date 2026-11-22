"""Santa 01 - FINAL COMPLETE ANIMATION, single-file Blender Python deliverable.

WHAT THIS CONTAINS
  1. Original teapot-follow + subtle secondary motion (coat, feet, hat, body)
  2. Ease in/out of existing pour animation (no redesigned kettle trajectory)
  3. Natural torso counterlean / kettle-side shoulder lift / cup-side shoulder dip
  4. Cup approaches lips and tilts ~17 deg with synchronized left-hand grip
  5. Tea fills as poured and disappears while Santa drinks (seamless loop)

HOW TO RUN
  (A) Open ORIGINAL santa01.blend in Blender, choose Scripting > Open,
      open THIS .py file and click Run Script / Alt+P.
  (B) Or from terminal: blender -b santa01.blend --python-exit-code 1 \
                          -P santa01_final_animation.py

REQUIREMENTS
  - Blender 4.4/5.x with its built-in Python (bpy)
  - ORIGINAL saved santa01.blend with Santa01_Rig and Santa01 mesh
  - No helper Python files, ZIP packages, external modules, or internet needed.

OUTPUT
  A NEW santa01_FINAL_ANIMATED.blend alongside your source .blend.
  Original file is NOT overwritten. Open the new file; press Spacebar to play.

The embedded stages below are the exact prior animation-editing stages, not a
new redesign. All keyframes are baked into the resulting .blend scene.
"""

from pathlib import Path
import sys
import tempfile
import types

try:
    import bpy
except ImportError as exc:
    raise RuntimeError('Run this script INSIDE Blender (Scripting or blender -P); not plain Python.') from exc


def _make_module(name, source):
    """Load a self-contained script stage as a Python module (no extra .py files)."""
    module = types.ModuleType(name)
    module.__file__ = str(Path(__file__).resolve()) if '__file__' in globals() else str(Path(bpy.data.filepath).resolve())
    sys.modules[name] = module
    exec(compile(source, module.__file__, 'exec'), module.__dict__)
    return module


def _output_name(source):
    output = source.with_name('santa01_FINAL_ANIMATED.blend')
    if not output.exists():
        return output
    for i in range(2, 1000):
        candidate = source.with_name(f'santa01_FINAL_ANIMATED_{i:03d}.blend')
        if not candidate.exists():
            return candidate
    raise RuntimeError('Too many output variants in this folder.')


def _execute_stage(module, destination):
    """Each stage keeps its prior pose / animation checks and save logic."""
    before = list(sys.argv)
    sys.argv = ['santa01_final_animation.py', '--', str(destination)]
    try:
        module.main()
        if not destination.is_file():
            raise RuntimeError('Stage ' + module.__name__ + ' did not create its Blender file.')
    finally:
        sys.argv = before


def main():
    source = Path(bpy.data.filepath).resolve()
    if not source.is_file():
        raise RuntimeError('Please OPEN and SAVE the ORIGINAL santa01.blend before running this script.')
    if source.suffix.lower() != '.blend':
        raise RuntimeError('The currently open file must be a .blend.')
    rig = bpy.data.objects.get('Santa01_Rig')
    if rig is None or bpy.data.objects.get('Santa01') is None:
        raise RuntimeError('This is not the original Santa01 scene; Santa01_Rig or Santa01 is missing.')
    if rig.get('secondary_motion') or rig.get('pour_posture_updated') or rig.get('santa_drink_updated'):
        raise RuntimeError('This file has already been animated by the update. Open the ORIGINAL santa01.blend.')
    if any(b in rig.data.bones for b in ('coat_hem', 'hat_tip')):
        raise RuntimeError('The rig already has secondary bones. Open ORIGINAL santa01.blend.')
    if bpy.context.scene.frame_start != 1 or bpy.context.scene.frame_end != 300:
        raise RuntimeError('Expected the original 300-frame Santa 01 animation.')

    final = _output_name(source)
    print('\n[Santa final] Source: ', source, flush=True)
    print('[Santa final] Output: ', final, flush=True)

    _make_module('secondary_motion', _SECONDARY_SOURCE)
    stages = [
        ('teapot & secondary motion', _make_module('_santa_teapot_stage', _TEAPOT_SOURCE)),
        ('ease in/out', _make_module('_santa_ease_stage', _EASE_SOURCE)),
        ('natural shoulders', _make_module('_santa_shoulder_stage', _SHOULDER_SOURCE)),
        ('cup drink & disappearing tea', _make_module('_santa_drink_stage', _DRINK_SOURCE)),
    ]
    try:
        with tempfile.TemporaryDirectory(prefix='santa_final_animation_') as tmp:
            for i, (label, stage) in enumerate(stages, 1):
                destination = final if i == len(stages) else Path(tmp) / f'stage_{i:02d}.blend'
                print(f'\n[Santa final] Stage {i}/4: {label} ...', flush=True)
                _execute_stage(stage, destination)
    finally:
        sys.modules.pop('secondary_motion', None)
        for _, module in stages:
            sys.modules.pop(module.__name__, None)
    print('\n[Santa final] SUCCESS. Open this file and press Spacebar:')
    print(final, flush=True)
    # In the Blender UI, we are now already looking at the final scene.
    # The saved output file includes all baked animation keyframes.




# ========== Embedded original animation source stages ==========

_SECONDARY_SOURCE = r'''
"""Secondary animation for the existing Santa01/Santa02 Blender characters.

Adds a few lightweight deformation bones (coat hem, sleeves and hat tip),
reweights only the relevant garment vertices, and keys gentle follow-through.
These are ordinary skeletal keys so they can be exported to GLB / USDZ.

The original animation, face, hands, props, and choreography are preserved.
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
    """Idempotently install cloth/hat control bones and smooth garment weights.

    This works either on the freshly generated Santa01 or on a saved original
    .blend used to construct Santa02. No simulated cloth/constraints required.
    """
    import bpy
    from mathutils import Vector

    if all(name in rig.data.bones for name in SECONDARY_BONES):
        return  # Santa02 reuses the already-upgraded Santa01 character
    if any(name in rig.data.bones for name in SECONDARY_BONES):
        raise RuntimeError('Partially installed secondary rig: restore the original file and rerun.')

    # Give the coat and sleeves their own pivot points. Keep the hat tip a child
    # of head: it *always* follows the head and just adds a delayed wobble.
    specs = [('coat_hem', (0, 0, .74), (0, 0, .95), 'hips'),
             ('hat_tip', (.22, .067, 2.095), (.33, .048, 1.89), 'head')]
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

    # Material flags let us distinguish red coat and sleeves from adjacent
    # skin, groceries and props even though Santa is one combined mesh.
    mesh = character.data
    flags = bytearray(len(mesh.vertices))
    fabric = {'Crimson_velvet': 1, 'Ivory_plush_fur': 2}
    for poly in mesh.polygons:
        mat = mesh.materials[poly.material_index]
        mask = fabric.get(mat.name, 0)
        if mask:
            for idx in poly.vertices:
                flags[idx] |= mask

    group_names = {vg.index: vg.name for vg in character.vertex_groups}
    counts = {name: 0 for name in SECONDARY_BONES}
    for vertex in mesh.vertices:
        flag = flags[vertex.index]
        if not flag:
            continue
        originals = [(group_names[g.group], g.weight) for g in vertex.groups]
        owners = {name for name, value in originals if value > .01}
        x, y, z = vertex.co
        target, influence = None, 0.0
        # Cap crown and pompom: blend head -> flexible hat tip. The front fur
        # brim stays head-bound. Restrict to head-only red/fur vertices.
        if owners == {'head'} and z > 1.82:
            if flag & 1 and z > 1.91:
                along = _clamp((x - .065) / .235)
                elevation = _clamp((z - 1.92) / .10)
                influence = .85 * along * elevation
            elif flag & 2 and x > .19 and z > 1.83:
                # Pompom falls below the red tip and should swing with it.
                influence = .92 * _clamp((x - .19) / .105)
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


def apply_secondary_pose(rig, frame, final_frame, activity=0.0):
    """Pose a lightweight loopable secondary layer; call before solving arms.

    `activity` ranges 0..1, indicating how far the main gesture has progressed.
    The shape is periodic and the first/last frame are identical for looping AR.
    """
    from mathutils import Quaternion, Vector

    t = (frame - 1) / (final_frame - 1)
    phase = 0.0 if frame == final_frame else math.tau * t
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


def keyframe_secondary(rig, frame):
    """Bake the extra motion into native rig animation channels for export."""
    for name in ANIMATED_BONES:
        bone = rig.pose.bones[name]
        bone.keyframe_insert('rotation_quaternion', frame=frame, group=name)
        if name in FOOT_BONES:
            bone.keyframe_insert('location', frame=frame, group=name)
'''

_TEAPOT_SOURCE = r'''
"""Bake secondary movement while making Santa 01's kettle follow his right hand.

Runs with Blender's bundled Python from the *original* santa01.blend:
    blender -b santa01.blend --python-exit-code 1 -P fix_santa_teapot.py -- output.blend

This modifies a COPY and saves the output; the original is untouched.
The original pouring choreography is preserved. We sample the difference in
right-hand pose caused by secondary body motion and apply exactly that rigid
transform to the keyed kettle pose for every frame. No physics or constraints.
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Quaternion, Vector

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from secondary_motion import (ANIMATED_BONES, FOOT_BONES,
                              apply_secondary_pose, ensure_secondary_rig,
                              keyframe_secondary)


def smooth01(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def ramp(frame, start, end):
    return smooth01((frame - start) / (end - start))


def neutralize_secondary(rig):
    """Remove the last baked secondary pose before measuring the hand baseline.

    After keying frame N, Blender holds that key at frame N+1 until the next
    key is inserted; ignoring this would accumulate a small offset each frame.
    The original Santa01 scene has no motion on these controls.
    """
    for name in ANIMATED_BONES:
        pb = rig.pose.bones[name]
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = Quaternion((1, 0, 0, 0))
        if name in FOOT_BONES:
            pb.location = Vector((0, 0, 0))


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    if len(args) != 1:
        raise RuntimeError('Expected output .blend path after --')
    output = Path(args[0]).resolve()
    source = Path(bpy.data.filepath).resolve()
    if source == output:
        raise RuntimeError('Choose a different output path to preserve the original')

    rig = bpy.data.objects.get('Santa01_Rig')
    santa = bpy.data.objects.get('Santa01')
    if not rig or not santa:
        raise RuntimeError('Open the ORIGINAL santa01.blend (with Santa01 and Santa01_Rig)')
    if rig.animation_data is None or rig.animation_data.action is None:
        raise RuntimeError('Original Santa01 animation is missing')
    if 'kettle' not in rig.pose.bones or 'hand.R' not in rig.pose.bones:
        raise RuntimeError('The scene is missing the kettle or right-hand bone')
    if any(b in rig.data.bones for b in ('coat_hem', 'hat_tip')):
        raise RuntimeError('The source has already been baked; use original santa01.blend instead')
    if 'secondary_motion' not in sys.modules:
        raise RuntimeError('The embedded secondary-motion module did not load')

    scene = bpy.context.scene
    ensure_secondary_rig(rig, santa)
    deform = next((m for m in santa.modifiers if m.type == 'ARMATURE'), None)
    former_visible = deform.show_viewport if deform else None
    if deform:
        deform.show_viewport = False  # substantial performance improvement for baking

    try:
        frame_start, frame_end = scene.frame_start, scene.frame_end
        for frame in range(frame_start, frame_end + 1):
            scene.frame_set(frame)
            neutralize_secondary(rig)
            bpy.context.view_layer.update()

            # Capture the original animation, including the tilt/pour, first.
            original_hand = rig.pose.bones['hand.R'].matrix.copy()
            original_kettle = rig.pose.bones['kettle'].matrix.copy()

            kettle_activity = ramp(frame, 24, 60) * (1 - ramp(frame, 132, 168))
            cup_activity = ramp(frame, 168, 204) * (1 - ramp(frame, 240, 276))
            apply_secondary_pose(rig, frame, frame_end, max(kettle_activity, cup_activity))
            bpy.context.view_layer.update()

            # If the body sway makes the hand rotate or move, perform the exact
            # same world-space motion on the kettle. This maintains its grip.
            hand_after = rig.pose.bones['hand.R'].matrix.copy()
            hand_delta = hand_after @ original_hand.inverted()
            rig.pose.bones['kettle'].matrix = hand_delta @ original_kettle
            bpy.context.view_layer.update()
            kettle = rig.pose.bones['kettle']
            for channel in ('location', 'rotation_quaternion', 'scale'):
                kettle.keyframe_insert(data_path=channel, frame=frame, group='kettle')
            keyframe_secondary(rig, frame)
            if frame % 60 == 0 or frame == frame_end:
                print('[Santa teapot] Baked frame {}/{}'.format(frame, frame_end), flush=True)
    finally:
        if deform:
            deform.show_viewport = former_visible

    scene.frame_set(scene.frame_start)
    rig['teapot_hand_follow'] = 'Kettle follows right hand secondary sway; original pour preserved'
    rig['secondary_motion_baked'] = 'Body, clothing, feet, hat and teapot-follow keyframes'
    bpy.context.preferences.filepaths.save_version = 0
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output), compress=True)
    if not output.is_file():
        raise RuntimeError('Could not save ' + str(output))
    print('[Santa teapot] READY: ' + str(output), flush=True)


if __name__ == '__main__':
    main()
'''

_EASE_SOURCE = r'''
"""Non-destructive timing-only ease for the previous Santa 01 teapot-follow animation.

Run from Blender (NOT normal Python), using the already-working
santa01_READY_with_teapot.blend as source:

  blender -b santa01_READY_with_teapot.blend --python-exit-code 1 \
      -P ease_existing_santa.py -- santa01_READY_EASED.blend

This does not calculate any new poses and does not alter any animated value.
It ONLY moves the *times* of the existing keys. All channels, including the
right hand, kettle, torso, clothing, feet, cup, head and tea stream, use the
same time mapping. There are no new arm paths, prop positions, IK solutions,
rotations or cloth weights.

Each gesture window receives a gentle combination of the original timing and
a quintic ease-in/ease-out. Per-frame keys stay LINEAR between retimed keys,
so their densely baked bone animations cannot develop Bezier overshoot.
"""

import sys
from pathlib import Path

import bpy

# 0.0 = prior animation; 1.0 = full quintic time easing.
# 0.50 gently eases existing motion further while respecting its choreography.
EASE_STRENGTH = 0.50

# The intervals and their original choreography were taken directly from the
# *previous* Santa 01 build, not the abandoned relaxed-pour redesign.
# Retiming all of them together keeps the hand, pot and tea synchronized.
GESTURE_MARKERS = (1.0, 24.0, 60.0, 132.0, 168.0, 204.0, 240.0, 276.0, 300.0)


def smootherstep(u):
    u = max(0.0, min(1.0, u))
    return u * u * u * (u * (6.0 * u - 15.0) + 10.0)


def inverse_smootherstep(u):
    """Find the new time at which a source pose should appear."""
    if u <= 0.0:
        return 0.0
    if u >= 1.0:
        return 1.0
    left, right = 0.0, 1.0
    for _ in range(35):
        middle = (left + right) * .5
        if smootherstep(middle) < u:
            left = middle
        else:
            right = middle
    return .5 * (left + right)


def ease_frame(source_time):
    """Only move when a value happens; never change the value itself."""
    for a, b in zip(GESTURE_MARKERS[:-1], GESTURE_MARKERS[1:]):
        if a <= source_time <= b:
            u = (source_time - a) / (b - a)
            eased = (1.0 - EASE_STRENGTH) * u + EASE_STRENGTH * inverse_smootherstep(u)
            return a + eased * (b - a)
    return source_time


def action_curves(obj):
    """Supports legacy Blender actions and layered/slot actions (Blender 4/5)."""
    animation = obj.animation_data
    if animation is None or animation.action is None:
        return []
    action = animation.action
    # Blender 3/4 legacy action
    try:
        if hasattr(action, 'fcurves'):
            legacy_curves = list(action.fcurves)
            if legacy_curves:
                return legacy_curves
    except (AttributeError, RuntimeError):
        pass
    # Blender 4.4+/5 layered action
    try:
        from bpy_extras.anim_utils import action_get_channelbag_for_slot
        bag = action_get_channelbag_for_slot(action, animation.action_slot)
        if bag is not None:
            return list(bag.fcurves)
    except (ImportError, AttributeError, RuntimeError):
        pass
    # API fallback for Blender versions with action.layers and channelbags
    try:
        curves = []
        slot = animation.action_slot
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    if bag.slot == slot:
                        curves.extend(list(bag.fcurves))
        if curves:
            return curves
    except (AttributeError, RuntimeError):
        pass
    raise RuntimeError('Cannot access the action F-curves in this Blender version')


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    if len(args) != 1:
        raise RuntimeError('Expected output .blend path after --')
    output = Path(args[0]).resolve()
    source = Path(bpy.data.filepath).resolve()
    if not source.is_file() or source == output:
        raise RuntimeError('Open a previous, saved Santa .blend; output must be a different path')

    rig = bpy.data.objects.get('Santa01_Rig')
    if rig is None or not rig.animation_data or not rig.animation_data.action:
        raise RuntimeError('Cannot find the original animated Santa01_Rig')
    if not rig.get('teapot_hand_follow'):
        raise RuntimeError('This file is not the previous teapot-follow version. Use santa01_READY_with_teapot.blend')
    if rig.get('ease_only_version'):
        raise RuntimeError('This file is already eased. Use the previous teapot-follow source to avoid double easing')
    if 'kettle' not in rig.pose.bones or 'hand.R' not in rig.pose.bones:
        raise RuntimeError('Missing hand or kettle bone')

    scene = bpy.context.scene
    if scene.frame_start != 1 or scene.frame_end != 300:
        raise RuntimeError('Expected the original 1..300-frame animation')

    curves = action_curves(rig)
    if len(curves) < 3:
        raise RuntimeError('Too few animation curves found; refusing to edit')

    # Reuse the same mapping for every curve and every channel. Keyframe values
    # remain numerically identical, and every source pose remains on its
    # original spatial path. Only its time of occurrence changes.
    moved = 0
    for fc in curves:
        for key in fc.keyframe_points:
            old_time = float(key.co.x)
            new_time = ease_frame(old_time)
            dx = new_time - old_time
            key.co.x = new_time
            key.handle_left.x += dx
            key.handle_right.x += dx
            key.interpolation = 'LINEAR'  # dense baked keys, no spatial overshoot
            if abs(dx) > 1e-8:
                moved += 1
        fc.update()

    scene.frame_set(scene.frame_start)
    rig['ease_only_version'] = 'Timing-only quintic ease in/out of previous teapot-follow animation'
    rig['ease_strength'] = EASE_STRENGTH
    rig['original_motion_preserved'] = 'No pose, kettle path, arm positions, or garment weights modified'
    bpy.context.preferences.filepaths.save_version = 0
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output), compress=True)
    if not output.is_file():
        raise RuntimeError('Could not save ' + str(output))
    print('[Santa timing] Adjusted {} timing keys across {} F-curves'.format(moved, len(curves)), flush=True)
    print('[Santa timing] READY: ' + str(output), flush=True)


if __name__ == '__main__':
    main()
'''

_SHOULDER_SOURCE = r'''
"""Add very subtle, reference-informed shoulder/posture motion to Santa 01.

Source: the PREVIOUS eased teapot-follow scene, NOT the discarded
SWAY / CUP-CATCH scene and NOT the discarded smooth-pour redesign.

    blender -b santa01_READY_EASED.blend --python-exit-code 1 \
        -P bake_santa_shoulder_lean.py -- santa01_READY_NATURAL_SHOULDERS.blend

Changes ONLY the torso/shoulders and the arm joint solves necessary to keep
both original hand+prop world-space poses. The leg motion, cup trajectory,
kettle trajectory, tea stream, hat and garment settings stay as before.

An ergonomic pouring gesture tends to involve coordinated trunk / shoulder
movement during the lifting and pouring phases. Here the pot-side shoulder
rises slightly and the cup-side shoulder drops, with ~2 degrees maximum
combined upper-body counterlean. Animation follows the old lift-and-lower
choreography and eases to zero at the beginning and end.
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

# Edit these two values to adjust only the posture.
SPINE_LEAN_DEGREES = 0.75
CHEST_LEAN_DEGREES = 1.20

# Same original gesture windows from Santa 01; no cup/prop changes.
POT_LIFT_START, POT_LIFT_END = 24, 60
POT_LOWER_START, POT_LOWER_END = 132, 168

SHOULDERS = {'L': Vector((.265, 0, 1.43)), 'R': Vector((-.265, 0, 1.43))}
UPPER, LOWER = 0.31, 0.30


def smootherstep(t):
    t = max(0.0, min(1.0, float(t)))
    return t * t * t * (t * (6 * t - 15) + 10)


def ramp(frame, a, b):
    return smootherstep((frame - a) / (b - a))


def angle_about_joint(matrix, degrees):
    """Tilt in ARMATURE space about world-Y, pivoting at a bone's posed head.

    A positive angle makes Santa lean towards his cup side (+X), subtly
    lowering the cup-side shoulder (+X) and lifting the teapot shoulder (-X).
    """
    pivot = matrix.translation
    transform = Matrix.Translation(pivot) @ Matrix.Rotation(math.radians(degrees), 4, 'Y') @ Matrix.Translation(-pivot)
    return transform @ matrix


def elbow_for(side, wrist, shoulder):
    """Use Santa 01's existing two-bone IK construction, not a new pose style."""
    direction = wrist - shoulder
    d = min(direction.length, UPPER + LOWER - 0.001)
    if d < 1.0e-6:
        raise RuntimeError('Unexpected zero-length arm direction')
    unit_dir = direction.normalized()
    a = (UPPER * UPPER - LOWER * LOWER + d * d) / (2.0 * d)
    guide = Vector((1 if side == 'L' else -1, .08, -.5))
    perp = (guide - unit_dir * guide.dot(unit_dir)).normalized()
    return shoulder + unit_dir * a + perp * math.sqrt(max(0.0, UPPER * UPPER - a * a))


def rigid_pose(rig, name, head, rotation):
    rest = rig.data.bones[name]
    rig.pose.bones[name].matrix = (
        Matrix.Translation(head) @ rotation.to_4x4() @
        Matrix.Translation(-rest.head_local) @ rest.matrix_local
    )
    bpy.context.view_layer.update()


def orient_segment(rig, name, start, end):
    rest = rig.data.bones[name]
    rest_axis = rest.tail_local - rest.head_local
    target_axis = end - start
    if target_axis.length < 0.001:
        raise RuntimeError('Unexpected zero-length segment ' + name)
    rot = rest_axis.rotation_difference(target_axis).to_matrix()
    rigid_pose(rig, name, start, rot)


def sample_pose(rig):
    """Capture local F-curve channels: portable across Blender 4.x and 5.x."""
    return {pb.name: (pb.location.copy(), pb.rotation_quaternion.copy(), pb.scale.copy())
            for pb in rig.pose.bones}


def check_matrix_close(a, b, what, frame, tolerance=0.0003):
    # Catch accidental movement of held props; only hand arm joint poses may
    # change due to shoulder repositioning, not their original goals.
    mismatch = max(abs(a[i][j] - b[i][j]) for i in range(4) for j in range(4))
    if mismatch > tolerance:
        raise RuntimeError('{} moved unexpectedly at frame {} (error {:.6g})'.format(what, frame, mismatch))


def main():
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    if len(argv) != 1:
        raise RuntimeError('Pass a single output .blend path after --')
    source = Path(bpy.data.filepath).resolve()
    destination = Path(argv[0]).resolve()
    if not source.is_file() or destination == source:
        raise RuntimeError('Open the saved eased Santa source; output must be a different path')

    rig = bpy.data.objects.get('Santa01_Rig')
    if rig is None or rig.animation_data is None or rig.animation_data.action is None:
        raise RuntimeError('The source has no animated Santa01_Rig')
    if not rig.get('teapot_hand_follow') or not rig.get('ease_only_version'):
        raise RuntimeError('Use the earlier santa01_READY_EASED.blend (teapot-follow + easing), not the latest sway version')
    if rig.get('pour_posture_updated'):
        raise RuntimeError('Posture has already been applied. Use the prior eased Santa as input')
    scene = bpy.context.scene
    if scene.frame_start != 1 or scene.frame_end != 300:
        raise RuntimeError('This animation expects frames 1 to 300')
    for part in ('spine','chest','upper_arm.L','upper_arm.R','forearm.L','forearm.R','hand.L','hand.R','cup','kettle'):
        if part not in rig.pose.bones:
            raise RuntimeError('Missing expected bone: ' + part)

    # The mesh skin modifier is expensive to evaluate for every sampled pose.
    # It has no bearing on the armature animation itself.
    character = bpy.data.objects.get('Santa01')
    deform = next((m for m in character.modifiers if m.type == 'ARMATURE'), None) if character else None
    original_deform_visibility = deform.show_viewport if deform else None
    if deform:
        deform.show_viewport = False

    old_action = rig.animation_data.action
    old_action.use_fake_user = True
    original_frame = scene.frame_current
    sampled = []

    # SAMPLE BEFORE editing action. Each iteration reevaluates the unchanged
    # previous animation, so no extra movement accumulates across frames.
    for frame in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        original = {name: rig.pose.bones[name].matrix.copy()
                    for name in ('hand.L', 'hand.R', 'cup', 'kettle')}
        amount = ramp(frame, POT_LIFT_START, POT_LIFT_END) * (1.0 - ramp(frame, POT_LOWER_START, POT_LOWER_END))

        # Counterlean raises the kettle shoulder and gently drops the cup side.
        # Use separate upper-spine and chest rotations so the torso bends softly.
        if amount > 1.0e-8:
            spine = rig.pose.bones['spine']
            spine.matrix = angle_about_joint(spine.matrix.copy(), amount * SPINE_LEAN_DEGREES)
            bpy.context.view_layer.update()
            chest = rig.pose.bones['chest']
            chest.matrix = angle_about_joint(chest.matrix.copy(), amount * CHEST_LEAN_DEGREES)
            bpy.context.view_layer.update()

            # Rebuild shoulders/upper arms with the old IK guide, ending at the
            # exact old wrist positions. No new teapot/cup or hand trajectories.
            chest_deform = rig.pose.bones['chest'].matrix @ rig.data.bones['chest'].matrix_local.inverted()
            for side in ('R','L'):
                shoulder = chest_deform @ SHOULDERS[side]
                wrist = original['hand.' + side].translation.copy()
                elbow = elbow_for(side, wrist, shoulder)
                orient_segment(rig, 'upper_arm.'+side, shoulder, elbow)
                orient_segment(rig, 'forearm.'+side, elbow, wrist)
                rig.pose.bones['hand.'+side].matrix = original['hand.'+side]
                bpy.context.view_layer.update()
            # Props were never changed; double-check the grip cannot pop off.
            for name in ('hand.L','hand.R','cup','kettle'):
                check_matrix_close(rig.pose.bones[name].matrix, original[name], name, frame)

        sampled.append(sample_pose(rig))
        if frame in (1, 24, 60, 100, 132, 168, 204, 300):
            print('[shoulders] Sampled {}/300, lean = {:.3f}'.format(frame, amount), flush=True)

    # The prior easing has subframe keys. Baking all existing poses to a clean
    # action avoids retaining fractional keys that could make new shoulder
    # keyframes jitter as Blender interpolates between them.
    rig.animation_data.action = None
    for frame, pose in enumerate(sampled, scene.frame_start):
        scene.frame_set(frame)
        for bone_name, (loc, rot, scl) in pose.items():
            bone = rig.pose.bones[bone_name]
            bone.rotation_mode = 'QUATERNION'
            bone.location = loc
            bone.rotation_quaternion = rot
            bone.scale = scl
            bone.keyframe_insert(data_path='location', frame=frame, group=bone_name)
            bone.keyframe_insert(data_path='rotation_quaternion', frame=frame, group=bone_name)
            bone.keyframe_insert(data_path='scale', frame=frame, group=bone_name)
        if frame % 75 == 0:
            print('[shoulders] Saved keys {}/300'.format(frame), flush=True)

    new_action = rig.animation_data.action
    if new_action is None:
        raise RuntimeError('Blender did not create a new action')
    new_action.name = 'Santa01_Eased_Pour_Natural_Shoulders'
    new_action.use_fake_user = True
    # Linear frame-by-frame samples preserve the previous eased motion without
    # Bezier overshoot or abrupt new key shapes.
    try:
        from bpy_extras.anim_utils import action_get_channelbag_for_slot
        bag = action_get_channelbag_for_slot(new_action, rig.animation_data.action_slot)
        curves = list(bag.fcurves) if bag is not None else []
    except (ImportError, AttributeError, RuntimeError):
        try:
            curves = list(new_action.fcurves)
        except (AttributeError, RuntimeError):
            curves = []
    for fc in curves:
        for key in fc.keyframe_points:
            key.interpolation = 'LINEAR'
        fc.update()

    scene.frame_set(1)
    if deform:
        deform.show_viewport = original_deform_visibility
    rig['pour_posture_updated'] = 'Subtle upper torso counterlean; cup-side shoulder drops and kettle-side shoulder rises'
    rig['posture_source'] = 'Previous teapot-follow + easing animation (no extra leg sway or cup lift)'
    rig['spine_lean_degrees'] = SPINE_LEAN_DEGREES
    rig['chest_lean_degrees'] = CHEST_LEAN_DEGREES
    bpy.context.preferences.filepaths.save_version = 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(destination), compress=True)
    if not destination.is_file():
        raise RuntimeError('Could not save finished Blender scene: ' + str(destination))
    print('[shoulders] READY: ' + str(destination), flush=True)

if __name__ == '__main__':
    main()
'''

_DRINK_SOURCE = r'''
"""Finish Santa01's drink gesture on top of NATURAL_SHOULDERS scene.

This script preserves the existing kettle, posture, clothing, legs, hat and
pouring actions. It edits only the left arm/cup/grip and the tea/steam:

- glass starts empty and fills when the tea is poured
- as cup reaches mouth, glass is brought gently closer and tipped toward lips
- left hand receives the identical rigid transform as glass
- left elbow/forearm solve to the newly moved wrist from existing shoulder
- the liquid drains WHILE Santa sips, not at the loop reset
- 1st and last frame have an empty, upright glass (seamless loop)

Designed to run with Blender 4.4/5.x bundled bpy:
    blender -b santa01_READY_NATURAL_SHOULDERS.blend --python-exit-code 1 \
      -P bake_santa_drink_from_natural.py -- santa01_READY_DRINKS_TEA.blend
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

# User-tuneable. The small glass already reaches face level at frame 204.
# Santa faces the -Y direction. A NEGATIVE X rotation tips the rim toward
# the mouth at approximately (0, -0.190, 1.644).
CUP_TILT_DEGREES = 17.0
LIP_APPROACH = Vector((-.012, .075, -.015))  # X, Y (towards face), Z

# Frame timing is based on the original 300-frame / 24 FPS cycle.
APPROACH_START, APPROACH_END = 199, 217
APPROACH_RETURN_START, APPROACH_RETURN_END = 248, 266
TILT_START, TILT_END = 215, 229
TILT_RETURN_START, TILT_RETURN_END = 240, 255
DRINK_START, DRINK_FINISH = 217, 248
FILL_START, FILL_FINISH = 65, 127

# Original character upper/lower arm measurements and shoulder anchor.
SHOULDER_L = Vector((.265, 0, 1.43))
UPPER, LOWER = .31, .30


def smootherstep(t):
    t = max(0.0, min(1.0, float(t)))
    return t * t * t * (t * (6 * t - 15) + 10)


def ramp(frame, a, b):
    return smootherstep((frame - a) / (b - a))


def factor(frame, start, end, return_start, return_end):
    return ramp(frame, start, end) * (1.0 - ramp(frame, return_start, return_end))


def drink_level(frame):
    """The cup is empty both before first pour AND at the loop boundary."""
    fill = ramp(frame, FILL_START, FILL_FINISH)
    consumed = ramp(frame, DRINK_START, DRINK_FINISH)
    return max(0.0, fill * (1.0 - consumed))


def elbow_for(wrist, shoulder):
    direction = wrist - shoulder
    d = min(direction.length, UPPER + LOWER - 0.001)
    if d < 1.0e-5:
        raise RuntimeError('Left hand got too close to shoulder')
    along = direction.normalized()
    a = (UPPER * UPPER - LOWER * LOWER + d * d) / (2.0 * d)
    guide = Vector((1.0, .08, -.5))
    perp = (guide - along * guide.dot(along)).normalized()
    return shoulder + along * a + perp * math.sqrt(max(0.0, UPPER * UPPER - a * a))


def rigid_segment(rig, bone_name, start, end):
    rest = rig.data.bones[bone_name]
    old_axis = rest.tail_local - rest.head_local
    new_axis = end - start
    if new_axis.length < .001:
        raise RuntimeError('Unexpected degenerate left-arm segment: ' + bone_name)
    rot = old_axis.rotation_difference(new_axis).to_matrix()
    rig.pose.bones[bone_name].matrix = (
        Matrix.Translation(start) @ rot.to_4x4() @
        Matrix.Translation(-rest.head_local) @ rest.matrix_local
    )
    bpy.context.view_layer.update()


def get_action_curves(obj):
    action = obj.animation_data.action
    try:
        curves = list(action.fcurves)
        if curves:
            return curves
    except (AttributeError, RuntimeError):
        pass
    try:
        from bpy_extras.anim_utils import action_get_channelbag_for_slot
        bag = action_get_channelbag_for_slot(action, obj.animation_data.action_slot)
        if bag is not None:
            return list(bag.fcurves)
    except (ImportError, AttributeError, RuntimeError):
        pass
    try:
        curves = []
        slot = obj.animation_data.action_slot
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    if bag.slot == slot:
                        curves.extend(list(bag.fcurves))
        return curves
    except (AttributeError, RuntimeError):
        return []


def close_matrix(a, b, label, frame, tol=.0005):
    delta = max(abs(a[r][c] - b[r][c]) for r in range(4) for c in range(4))
    if delta > tol:
        raise RuntimeError('{} became detached at frame {} (diff {:.6f})'.format(label, frame, delta))


def sample_local_pose(rig):
    return {bone.name: (bone.location.copy(), bone.rotation_quaternion.copy(), bone.scale.copy())
            for bone in rig.pose.bones}


def main():
    args = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    if len(args) != 1:
        raise RuntimeError('Expected one output .blend path after --')
    source = Path(bpy.data.filepath).resolve()
    output = Path(args[0]).resolve()
    if not source.is_file() or source == output:
        raise RuntimeError('Open an existing natural-shoulders Santa file and choose a different output path')

    rig = bpy.data.objects.get('Santa01_Rig')
    if rig is None or rig.animation_data is None or rig.animation_data.action is None:
        raise RuntimeError('No animated Santa01_Rig was found in this scene')
    if not rig.get('pour_posture_updated'):
        raise RuntimeError('Source must be santa01_READY_NATURAL_SHOULDERS.blend (not older pour variations)')
    if rig.get('santa_drink_updated'):
        raise RuntimeError('This scene already contains the new drinking gesture; do not apply twice')

    scene = bpy.context.scene
    if scene.frame_start != 1 or scene.frame_end != 300:
        raise RuntimeError('Expected Santa 01 scene with frames 1 through 300')
    required = ('cup', 'hand.L', 'upper_arm.L', 'forearm.L',
                'liquid', 'aroma', 'chest', 'kettle', 'hand.R')
    for name in required:
        if name not in rig.pose.bones:
            raise RuntimeError('The Santa rig is missing required bone ' + name)

    # Temporarily disable skin modifier for fast, deterministic sampling.
    character = bpy.data.objects.get('Santa01')
    modifier = (next((mod for mod in character.modifiers if mod.type == 'ARMATURE'), None)
                if character else None)
    old_visibility = modifier.show_viewport if modifier else None
    if modifier:
        modifier.show_viewport = False

    original_frame = scene.frame_current
    old_action = rig.animation_data.action
    old_action.use_fake_user = True
    all_frames = []
    max_cup_hand_error = 0.0

    try:
        # SAMPLE first; don't edit the source action while using it to read
        # poses. The right arm, teapot, body, feet, head and clothes remain
        # untouched; we alter the cup/left wrist in the same coordinate frame.
        for frame in range(scene.frame_start, scene.frame_end + 1):
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            cup_old = rig.pose.bones['cup'].matrix.copy()
            hand_old = rig.pose.bones['hand.L'].matrix.copy()
            kettle_old = rig.pose.bones['kettle'].matrix.copy()
            right_hand_old = rig.pose.bones['hand.R'].matrix.copy()

            approach = factor(frame, APPROACH_START, APPROACH_END,
                              APPROACH_RETURN_START, APPROACH_RETURN_END)
            tip = factor(frame, TILT_START, TILT_END,
                         TILT_RETURN_START, TILT_RETURN_END)
            offset = LIP_APPROACH * approach
            angle = math.radians(-CUP_TILT_DEGREES * tip)
            pivot = cup_old.translation.copy()

            # A single rigid transform moves BOTH cup and grip. This is what
            # prevents fingers drifting away while the wrist rotates.
            delta = (
                Matrix.Translation(offset) @
                Matrix.Translation(pivot) @
                Matrix.Rotation(angle, 4, 'X') @
                Matrix.Translation(-pivot)
            )
            desired_cup = delta @ cup_old
            desired_hand = delta @ hand_old
            rig.pose.bones['cup'].matrix = desired_cup
            bpy.context.view_layer.update()

            # Two-bone left arm reaches the wrist while retaining the
            # natural-shoulder animation from the source file.
            chest = rig.pose.bones['chest']
            chest_transform = chest.matrix @ rig.data.bones['chest'].matrix_local.inverted()
            shoulder = chest_transform @ SHOULDER_L
            wrist = desired_hand.translation.copy()
            elbow = elbow_for(wrist, shoulder)
            rigid_segment(rig, 'upper_arm.L', shoulder, elbow)
            rigid_segment(rig, 'forearm.L', elbow, wrist)
            rig.pose.bones['hand.L'].matrix = desired_hand
            bpy.context.view_layer.update()

            # Verify no existing right-side or kettle choreography moves.
            close_matrix(rig.pose.bones['cup'].matrix, desired_cup, 'cup', frame)
            close_matrix(rig.pose.bones['hand.L'].matrix, desired_hand, 'left hand', frame)
            close_matrix(rig.pose.bones['kettle'].matrix, kettle_old, 'kettle', frame)
            close_matrix(rig.pose.bones['hand.R'].matrix, right_hand_old, 'right hand', frame)
            actual_transform = rig.pose.bones['hand.L'].matrix @ hand_old.inverted()
            max_cup_hand_error = max(
                max_cup_hand_error,
                max(abs(actual_transform[r][c] - delta[r][c]) for r in range(4) for c in range(4))
            )

            level = drink_level(frame)
            # The original tea is a single combined-mesh component whose
            # vertex group is driven by the 'liquid' bone. Bone local Y is
            # vertical. Shrink width only as liquid becomes almost empty.
            width = smootherstep(level / 0.06)
            rig.pose.bones['liquid'].scale = Vector((max(.001, width), max(.001, level), max(.001, width)))
            if frame >= DRINK_START:
                # Steam fades as the last sip is consumed, rather than
                # continuing to rise from a visibly empty glass.
                aroma = rig.pose.bones['aroma']
                fade = 1.0 - ramp(frame, 235, 255)
                aroma.scale = Vector(tuple(max(.001, a * fade) for a in aroma.scale))

            all_frames.append(sample_local_pose(rig))
            if frame in (1, 66, 125, 204, 216, 229, 242, 248, 255, 300):
                print('[drink] frame={} approach={:.2f} tilt={:.1f}deg tea={:.3f}'.format(
                    frame, approach, CUP_TILT_DEGREES * tip, level), flush=True)
    finally:
        if modifier:
            modifier.show_viewport = old_visibility

    if max_cup_hand_error > 0.0005:
        raise RuntimeError('Cup/hand rigid-grip error too large: {}'.format(max_cup_hand_error))
    # Extra loop tests: empty at both ends and the new cup keyframes are
    # unchanged there, so the scene does not pop when playback wraps.
    assert drink_level(1) == 0.0 and drink_level(300) == 0.0
    assert factor(1, APPROACH_START, APPROACH_END, APPROACH_RETURN_START, APPROACH_RETURN_END) == 0.0
    assert factor(300, APPROACH_START, APPROACH_END, APPROACH_RETURN_START, APPROACH_RETURN_END) == 0.0

    # Bake a separate complete action; source action remains stored as backup.
    rig.animation_data.action = None
    for frame, pose in enumerate(all_frames, scene.frame_start):
        scene.frame_set(frame)
        for bone_name, (loc, rot, scl) in pose.items():
            pb = rig.pose.bones[bone_name]
            pb.rotation_mode = 'QUATERNION'
            pb.location = loc
            pb.rotation_quaternion = rot
            pb.scale = scl
            pb.keyframe_insert(data_path='location', frame=frame, group=bone_name)
            pb.keyframe_insert(data_path='rotation_quaternion', frame=frame, group=bone_name)
            pb.keyframe_insert(data_path='scale', frame=frame, group=bone_name)
        if frame % 75 == 0:
            print('[drink] Baked {}/300 frames'.format(frame), flush=True)

    action = rig.animation_data.action
    if action is None:
        raise RuntimeError('No action was produced')
    action.name = 'Santa01_Natural_Shoulders_Drink_Cup_Tilt'
    action.use_fake_user = True
    # Key each frame linearly to keep our smootherstep-derived movement exact
    # and avoid unwanted Bezier overshooting during the lip contact.
    for fc in get_action_curves(rig):
        for key in fc.keyframe_points:
            key.interpolation = 'LINEAR'
        fc.update()

    scene.frame_set(1)
    rig['santa_drink_updated'] = 'Glass tips toward lips, left hand follows as rigid grip, tea empties while sipping'
    rig['drink_tilt_degrees'] = CUP_TILT_DEGREES
    rig['drink_liquid_timing'] = 'Empty frame 1, fill 65-127, drain 217-248, empty frame 300'
    rig['drink_base_source'] = 'Natural shoulders: preserves previous kettle, upper-body and teapot-follow motion'
    bpy.context.preferences.filepaths.save_version = 0
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output), compress=True)
    if not output.is_file():
        raise RuntimeError('Blender could not save ' + str(output))
    print('[drink] READY TO OPEN: {}'.format(output), flush=True)


if __name__ == '__main__':
    main()
'''


if __name__ == "__main__":
    main()
