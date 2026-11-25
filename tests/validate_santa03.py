"""Run with blender -b --python-exit-code 1 -P tests/validate_santa03.py."""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from edition_checks import check  # noqa: E402

check('santa03', 'Santa03_Offer_Bouquet', 193,
      holds=[('hand.R', 'mug'), ('hand.L', 'bouquet')],
      props=['mug', 'steam', 'bouquet'], translucent=True)

# A supporting hand below the flowers, rather than an encircling fist. Measure the actual mesh
# in the bouquet's rest frame; changing the arm pose must not hide a return of the old ring grip.
rig = bpy.data.objects['Santa03_Rig']
santa = bpy.data.objects['Santa03']
origin = rig.data.bones['bouquet'].head_local
group = santa.vertex_groups['hand.L'].index
glove = [v.co - origin for v in santa.data.vertices
         if any(g.group == group and g.weight > .999 for g in v.groups)]
assert glove and max(v.z for v in glove) < .085, 'Left glove reaches into the flowers'
angles = sorted(math.atan2(v.y, v.x) for v in glove)
largest_gap = max(b - a for a, b in zip(angles, angles[1:] + [angles[0] + math.tau]))
assert math.tau - largest_gap < math.radians(195), 'Left glove encircles the bouquet'

previous = None
heights = []
for frame in range(1, 194):
    bpy.context.scene.frame_set(frame)
    bouquet = rig.pose.bones['bouquet']
    deform = bouquet.matrix @ bouquet.bone.matrix_local.inverted()
    axis = (deform.to_3x3() @ Vector((0, 0, 1))).normalized()
    front = deform.to_3x3() @ Vector((0, -1, 0))
    rotation = deform.to_quaternion()
    wrist = rig.pose.bones['hand.L'].head.copy()
    assert bouquet.head.x > .40, (frame, 'Bouquet should stay beside Santa')
    assert axis.x > .20 and axis.z > .72, (frame, 'Bouquet should stay outward and above the hand')
    assert front.y < -.80, (frame, 'Open flower arrangement should face the guest')
    heights.append(bouquet.head.z)
    if previous:
        old_wrist, old_rotation = previous
        assert (wrist - old_wrist).length < .012, (frame, 'Wrist jumps during the offer')
        angle = rotation.rotation_difference(old_rotation).angle
        assert min(angle, math.tau - angle) < math.radians(3), (frame, 'Bouquet twists abruptly')
    previous = wrist, rotation
assert .15 < max(heights) - min(heights) < .28, 'Offer should raise the flowers to the viewer'
bpy.context.scene.frame_set(97)
offer = rig.pose.bones['bouquet']
direction = (offer.matrix @ offer.bone.matrix_local.inverted()).to_3x3() @ Vector((0, 0, 1))
assert offer.head.y < -.55 and offer.head.z > 1.28, 'Offer should reach forward at chest height'
assert direction.y < -.40, 'Offered flower heads should tip toward the viewer'
print('PASS: Santa03 one-sided support below the flowers and smooth forward offer to the viewer')
