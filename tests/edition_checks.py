"""Shared checks for Santa editions built with santa_kit.py (Santa 03 onwards)."""
import json
import struct
from pathlib import Path

import bpy
from pxr import Usd, UsdGeom, UsdShade, UsdSkel

ROOT = Path(__file__).resolve().parents[1]
TEA = ('cup', 'kettle', 'liquid', 'aroma', 'stream')


def check(version, action, frames, holds, props, translucent=False):
    """holds: (hand bone, prop bone) pairs that must stay locked together for the whole loop.
    props: prop bones whose skinned vertices must follow their bone rigidly."""
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

    samples = {}
    for group in props:
        index = santa.vertex_groups[group].index
        samples[group] = next(v.index for v in santa.data.vertices
                              if any(g.group == index and g.weight > .999 for g in v.groups))
    first, grips, rest = {}, {}, {}
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
            if frame == 1:
                grips[hand] = relative
            difference = relative - grips[hand]
            assert max(abs(x) for row in difference for x in row) < .0005, (frame, hand, prop, 'grip slipped')
        if frame == 1:
            first = pose
        for bone, matrix in pose.items():
            if max(abs(x) for row in matrix - first[bone] for x in row) > .001:
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
    page = (docs / (version + '.html')).read_text(encoding='utf-8')
    assert action in page
    for asset in (version + '.glb', version + '.usdz', version + '-poster.webp'):
        assert asset in page and (docs / asset).stat().st_size > 0
    print(f'PASS: {name} grips, loop closure, rigid props, skinning, textures, exports and page assets')
