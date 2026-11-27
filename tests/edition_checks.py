"""Shared checks for Santa editions built with santa_kit.py."""
import json
import struct
from pathlib import Path

import bpy
from mathutils.bvhtree import BVHTree
from pxr import Usd, UsdGeom, UsdShade, UsdSkel

ROOT = Path(__file__).resolve().parents[1]
TEA = ('cup', 'kettle', 'liquid', 'aroma', 'stream')
PAGES = {'santa03': 'Santa_Bouquet_Cafe', 'santa04': 'Santa_Landmark',
         'santa05': 'Santa_Mello', 'santa06': 'Santa_Yunqueen'}


def check_beard_clearance(scene, santa, cover=()):
    # The visible lower locks stay in front of the coat. Props can pass in front of them, and behind
    # props bound to the `cover` bones (Santa 02's shopping) the beard may tuck into the coat.
    mesh = santa.data
    torso_groups = {santa.vertex_groups[name].index for name in ('hips', 'spine', 'chest', 'neck')}
    torso_vertices = {v.index for v in mesh.vertices
                      if sum(g.weight for g in v.groups if g.group in torso_groups) > .98}
    coat_slots = {mesh.materials.find(name) for name in ('Crimson_velvet', 'Ivory_plush_fur')}
    coat_faces = [tuple(f.vertices) for f in mesh.polygons
                  if f.material_index in coat_slots and all(i in torso_vertices for i in f.vertices)]
    coat_vertices = sorted({i for face in coat_faces for i in face})
    coat_indices = {i: index for index, i in enumerate(coat_vertices)}
    coat_faces = [[coat_indices[i] for i in face] for face in coat_faces]
    beard_slot = mesh.materials.find('Silver_beard')
    beard_vertices = {i for face in mesh.polygons if face.material_index == beard_slot for i in face.vertices}
    beard_tips = [i for i in beard_vertices if mesh.vertices[i].co.z < 1.35
                  and mesh.vertices[i].co.y < -.232 and abs(mesh.vertices[i].co.x) < .16]
    assert coat_faces and beard_tips, 'Expected coat and lower beard geometry'
    cover_groups = {santa.vertex_groups[name].index for name in cover}
    cover_vertices = {v.index for v in mesh.vertices
                      if sum(g.weight for g in v.groups if g.group in cover_groups) > .5}
    cover_faces = [tuple(f.vertices) for f in mesh.polygons if all(i in cover_vertices for i in f.vertices)]
    cover_used = sorted({i for face in cover_faces for i in face})
    cover_indices = {i: index for index, i in enumerate(cover_used)}
    cover_faces = [[cover_indices[i] for i in face] for face in cover_faces]

    original_frame = scene.frame_current
    for frame in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(frame)
        posed = santa.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.vertices
        coat = BVHTree.FromPolygons([posed[i].co for i in coat_vertices], coat_faces)
        shield = BVHTree.FromPolygons([posed[i].co for i in cover_used], cover_faces) if cover_faces else None
        visible = 0
        for i in beard_tips:
            x, y, z = posed[i].co
            hit = coat.ray_cast((x, -2, z), (0, 1, 0))[0]
            hidden = shield is not None and shield.ray_cast((x, -2, z), (0, 1, 0), 2 + y)[0] is not None
            visible += hit is None or hit.y > y or hidden
        assert visible >= .95 * len(beard_tips), (santa.name, frame, 'The lower beard clips into the coat')
    scene.frame_set(original_frame)
    print(f'PASS: {santa.name} beard clearance throughout the loop', flush=True)


def check(version, action, frames, holds, props, translucent=False, grip_offsets=None, stationary_props=()):
    """holds: (hand bone, prop bone) pairs that must stay locked together for the whole loop.
    grip_offsets: rest-space offsets from wrists to fixed prop contact points for pivoting gloves.
    props and stationary_props: moving and planted prop bones whose vertices are skinned rigidly."""
    name = version.capitalize()
    bpy.ops.wm.open_mainfile(filepath=str(ROOT / (version + '.blend')))
    scene = bpy.context.scene
    rig = bpy.data.objects[name + '_Rig']
    santa = bpy.data.objects[name]
    assert rig.animation_data.action.name == action
    assert all(n not in rig.data.bones for n in TEA)
    assert all(im.packed_file for im in bpy.data.images if im.source == 'FILE')
    assert all(v.groups and abs(sum(g.weight for g in v.groups) - 1) < .0001 for v in santa.data.vertices)
    assert (scene.frame_start, scene.frame_end, scene.render.fps) == (1, frames, 24)
    check_beard_clearance(scene, santa)

    samples = {}
    for group in (*props, *stationary_props):
        index = santa.vertex_groups[group].index
        samples[group] = next(v.index for v in santa.data.vertices
                              if any(g.group == index and g.weight > .999 for g in v.groups))
    grip_points = {}
    for hand, offset in (grip_offsets or {}).items():
        bone = rig.data.bones[hand]
        grip_points[hand] = bone.matrix_local.inverted() @ (bone.head_local + offset)
    first, grips = {}, {}
    moved = set()
    for frame in range(1, frames + 1):
        scene.frame_set(frame)
        pose = {b.name: b.matrix.copy() for b in rig.pose.bones}
        chest = rig.pose.bones['chest']
        chest_deform = chest.matrix @ chest.bone.matrix_local.inverted()
        for side in 'LR':
            upper, fore, hand = [rig.pose.bones[n + '.' + side] for n in ('upper_arm', 'forearm', 'hand')]
            assert (upper.tail - fore.head).length < .0001, (frame, side, 'elbow')
            assert (fore.tail - hand.head).length < .0001, (frame, side, 'wrist')
            # The shoulders ride the swaying chest.
            assert (upper.head - chest_deform @ upper.bone.head_local).length < .0001, (frame, side, 'shoulder')
        for hand, prop in holds:
            relative = pose[prop].inverted() @ pose[hand]
            if hand in grip_points:
                relative = relative @ grip_points[hand]
            if frame == 1:
                grips[hand] = relative
            difference = relative - grips[hand]
            error = difference.length if hand in grip_points else max(
                abs(x) for row in difference for x in row)
            assert error < .0005, (frame, hand, prop, 'grip slipped')
        if frame == 1:
            first = pose
        for bone, matrix in pose.items():
            distance = max(abs(x) for row in matrix - first[bone] for x in row)
            if bone in stationary_props:
                assert distance < .0001, (frame, bone, 'planted prop moved')
            if distance > .001:
                moved.add(bone)
        if frame == frames:
            for bone, matrix in pose.items():
                assert max(abs(x) for row in matrix - first[bone] for x in row) < .0001, (bone, 'loop does not close')
        if frame in (1, frames // 2, frames):
            mesh = santa.evaluated_get(bpy.context.evaluated_depsgraph_get()).data
            for group, i in samples.items():
                bone = rig.pose.bones[group]
                expected = bone.matrix @ rig.data.bones[group].matrix_local.inverted() @ santa.data.vertices[i].co
                assert (mesh.vertices[i].co - expected).length < .0001, (frame, group, 'prop not skinned rigidly')
    assert {h for h, _ in holds} | set(props) <= moved | {'root'}, ('static', ({h for h, _ in holds} | set(props)) - moved)

    docs = ROOT / 'docs'
    raw = (docs / (version + '.glb')).read_bytes()
    assert struct.unpack_from('<4sII', raw) == (b'glTF', 2, len(raw))
    length, kind = struct.unpack_from('<I4s', raw, 12)
    assert kind == b'JSON'
    gltf = json.loads(raw[20:20 + length])
    assert [a['name'] for a in gltf['animations']] == [action]
    assert gltf['skins'] and gltf['images'] and all('bufferView' in image for image in gltf['images'])
    assert all('WEIGHTS_0' in p['attributes'] and 'JOINTS_0' in p['attributes']
               for m in gltf['meshes'] for p in m['primitives'])
    assert len(raw) < 16_000_000, 'GLB too large for a phone download'
    stage = Usd.Stage.Open(str(docs / (version + '.usdz')))
    assert any(p.IsA(UsdGeom.Mesh) for p in stage.Traverse())
    assert any(p.IsA(UsdSkel.Skeleton) for p in stage.Traverse())
    assert any(p.IsA(UsdSkel.Animation) and
               UsdSkel.Animation(p).GetTranslationsAttr().GetNumTimeSamples() > 1 for p in stage.Traverse())
    if translucent:
        assert any(s.GetIdAttr().Get() == 'UsdPreviewSurface' and s.GetInput('opacity') and
                   0 < s.GetInput('opacity').Get() < .2
                   for p in stage.Traverse() if p.IsA(UsdShade.Shader) for s in [UsdShade.Shader(p)])
    page = (docs / (PAGES[version] + '.html')).read_text(encoding='utf-8')
    assert action in page
    for asset in (version + '.glb', version + '-android.glb', version + '.usdz', version + '-poster.webp'):
        assert asset in page and (docs / asset).stat().st_size > 0
    # Scene Viewer closes on any extension outside its list; the Android copy must use none.
    assert b'extensions' not in (docs / (version + '-android.glb')).read_bytes()[:200000],         'Android GLB still uses glTF extensions'
    print(f'PASS: {name} grips, loop closure, rigid props, skinning, textures, exports and page assets')
