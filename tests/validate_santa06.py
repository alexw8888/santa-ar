"""Run with blender -b --python-exit-code 1 -P tests/validate_santa06.py."""
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from edition_checks import check  # noqa: E402

check('santa06', 'Santa06_Noodle_Chopsticks', 289,
      holds=[('hand.L', 'bowl'), ('hand.R', 'sticks')],
      props=['bowl', 'steam', 'sticks', 'stick', 'noodle.00', 'noodle.08',
             'duck_head', 'duck_feathers', 'duck_wing.L', 'duck_wing.R'],
      stationary_props=['duck'], translucent=True)

scene = bpy.context.scene
santa = bpy.data.objects['Santa06']
bones = bpy.data.objects['Santa06_Rig'].pose.bones
hand = bones['hand.R']
bowl = bones['bowl']
lower_tip_offset = Vector((.025, .060, .005)) + .27 * Vector((1, -.40, -.50)).normalized()
tip_local = hand.bone.matrix_local.inverted() @ (hand.bone.head_local + lower_tip_offset)

# Build the radial profile from the porcelain mesh, including the lip of the bowl.
mesh = santa.data
porcelain = mesh.materials.find('White porcelain bowl')
surface = {i for face in mesh.polygons if face.material_index == porcelain for i in face.vertices}
assert surface, 'Expected the porcelain bowl mesh'
bowl_points = np.array([mesh.vertices[i].co[:] for i in surface])
origin = np.array(bowl.bone.head_local)
origin[2] = bowl_points[:, 2].min()
bowl_points -= origin
heights, rings = np.unique(np.round(bowl_points[:, 2], 6), return_inverse=True)
outer_radii = np.zeros(len(heights))
np.maximum.at(outer_radii, rings, np.linalg.norm(bowl_points[:, :2], axis=1))

gloves = {}
for side in 'LR':
    name = 'hand.' + side
    group = santa.vertex_groups[name].index
    positions = np.array([v.co[:] for v in mesh.vertices if any(g.group == group and g.weight > .995 for g in v.groups)])
    assert len(positions), (name, 'Expected glove vertices')
    gloves[name] = positions

for frame in range(1, scene.frame_end + 1):
    scene.frame_set(frame)
    bowl_inverse = bowl.bone.matrix_local @ bowl.matrix.inverted()
    for name, positions in gloves.items():
        glove = bones[name]
        transform = np.array(bowl_inverse @ glove.matrix @ glove.bone.matrix_local.inverted())
        posed = positions @ transform[:3, :3].T + transform[:3, 3] - origin
        z = posed[:, 2]
        radial_clearance = np.linalg.norm(posed[:, :2], axis=1) - np.interp(z, heights, outer_radii)
        clearance = np.maximum.reduce([radial_clearance, z - heights[-1], -z])
        assert clearance.min() > .001, (frame, name, 'The glove clips into the bowl', clearance.min())
    tip = hand.matrix @ tip_local
    if frame in (73, 248):
        bowl_tip = np.array(bowl_inverse @ tip) - origin
        assert bowl_tip[2] < heights[-1] - .03 and np.linalg.norm(bowl_tip[:2]) < .12, (
            frame, 'The chopstick tips must dip inside the bowl')
    if 78 <= frame <= 249:
        assert (bones['noodle.00'].head - tip).length < .0001, (
            frame, 'The pinched noodles must follow the chopstick tips')

print('PASS: Santa06 gloves clear the bowl and noodles stay attached throughout the pinch')
