"""Write the Android copy of an exported GLB: the same file minus extensions Scene Viewer rejects.

python scene_viewer_glb.py santa01 [santa02 ...]   # docs/santaNN.glb -> docs/santaNN-android.glb

Google's Scene Viewer checks every glTF it opens and treats any extension outside a short list as
an error, so it closes as soon as it opens a model that uses KHR_materials_sheen, _specular,
_clearcoat or _emissive_strength. The in-page viewer renders those, so the pages keep the full GLB
for desktop and load this copy only on Android, where Scene Viewer downloads the page's model.
Geometry, skin, animation and textures are byte-for-byte the same; only material extensions go.
"""
import json, os, struct, sys

# Extensions Scene Viewer accepts (developers.google.com/ar/develop/scene-viewer).
SCENE_VIEWER_EXTENSIONS = {'KHR_materials_pbrSpecularGlossiness', 'KHR_materials_unlit',
                           'KHR_texture_transform'}
HERE = os.path.dirname(os.path.abspath(__file__))


def read_glb(path):
    data = open(path, 'rb').read()
    magic, version, length = struct.unpack_from('<4sII', data, 0)
    assert magic == b'glTF' and version == 2 and length == len(data), path
    json_len, json_type = struct.unpack_from('<I4s', data, 12)
    assert json_type == b'JSON', path
    gltf = json.loads(data[20:20 + json_len])
    return gltf, data[20 + json_len:]   # the remaining chunks (BIN), kept as they are


def write_glb(path, gltf, rest):
    text = json.dumps(gltf, separators=(',', ':')).encode()
    text += b' ' * (-len(text) % 4)
    header = struct.pack('<4sII', b'glTF', 2, 12 + 8 + len(text) + len(rest))
    with open(path, 'wb') as f:
        f.write(header + struct.pack('<I4s', len(text), b'JSON') + text + rest)


def strip(gltf):
    """Drop unsupported extensions from every material; return the names removed."""
    removed = set()
    for material in gltf.get('materials', []):
        extensions = material.get('extensions', {})
        for name in [n for n in extensions if n not in SCENE_VIEWER_EXTENSIONS]:
            del extensions[name]
            removed.add(name)
        if 'extensions' in material and not extensions:
            del material['extensions']
    for key in ('extensionsUsed', 'extensionsRequired'):
        kept = [n for n in gltf.get(key, []) if n in SCENE_VIEWER_EXTENSIONS]
        removed.update(n for n in gltf.get(key, []) if n not in SCENE_VIEWER_EXTENSIONS)
        if kept:
            gltf[key] = kept
        else:
            gltf.pop(key, None)
    # Anything left outside materials would still be rejected, so fail instead of shipping it.
    leftover = json.dumps(gltf)
    stray = {n for n in removed if n in leftover}
    assert not stray, ('Extensions used outside materials', stray)
    return removed


def write_android_glb(version, docs=os.path.join(HERE, 'docs')):
    src = os.path.join(docs, version + '.glb')
    dst = os.path.join(docs, version + '-android.glb')
    gltf, rest = read_glb(src)
    removed = strip(gltf)
    write_glb(dst, gltf, rest)
    print(f'[export] {version}-android.glb without', ', '.join(sorted(removed)) or 'nothing',
          os.path.getsize(dst), 'bytes', flush=True)
    return dst


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit('Pass one or more versions, for example: python scene_viewer_glb.py santa01')
    for version in sys.argv[1:]:
        write_android_glb(version)
