"""Render a studio portrait from santa_base.blend, with a close-up fiber groom.

blender -b santa_base.blend --python-exit-code 1 -P render_santa_head.py -- [draft] [both]
"""
import math
from pathlib import Path
import random
import sys

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Quaternion, Vector

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import santa_head as head
from santa_portrait_fit import CAMERAS
from santa_model import HEAD_SCALE, head_height, fit_portrait, fit_part


def keep_head(character):
    names = ('head', 'hat_tip', 'eye.L', 'eye.R')
    groups = {character.vertex_groups[name].index for name in names}
    head_group = character.vertex_groups['head'].index
    chest_group = character.vertex_groups['chest'].index
    mesh = bmesh.new()
    mesh.from_mesh(character.data)
    deform = mesh.verts.layers.deform.active
    body = [v for v in mesh.verts if groups.isdisjoint(v[deform].keys())]
    bmesh.ops.delete(mesh, geom=body, context='VERTS')
    for vertex in mesh.verts:
        weights = vertex[deform]
        drape = weights.get(chest_group, 0)
        if drape:
            # The portrait's isolated beard and fine groom move together with the head.
            weights[head_group] += drape
            del weights[chest_group]
    mesh.to_mesh(character.data)
    mesh.free()


def fiber_material(name, dark, light):
    material = bpy.data.materials.new(name)
    material.diffuse_color = (*light, 1)
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    info = nodes.new('ShaderNodeHairInfo')
    tone = nodes.new('ShaderNodeMixRGB')
    tone.inputs[1].default_value = (*dark, 1)
    tone.inputs[2].default_value = (*light, 1)
    links.new(info.outputs['Random'], tone.inputs[0])
    nodes.remove(nodes['Principled BSDF'])
    shader = nodes.new('ShaderNodeBsdfHairPrincipled')
    shader.parametrization = 'COLOR'
    roots = nodes.new('ShaderNodeValToRGB')
    roots.color_ramp.elements[0].color = (.79, .74, .69, 1)
    roots.color_ramp.elements[1].position = .69
    variation = nodes.new('ShaderNodeMixRGB')
    variation.blend_type = 'MULTIPLY'
    variation.inputs[0].default_value = 1
    links.new(info.outputs['Intercept'], roots.inputs['Fac'])
    links.new(tone.outputs['Color'], variation.inputs[1])
    links.new(roots.outputs['Color'], variation.inputs[2])
    links.new(variation.outputs['Color'], shader.inputs['Color'])
    local = nodes.new('ShaderNodeAttribute')
    local.attribute_name = 'Groom color'
    shade = nodes.new('ShaderNodeMixRGB')
    shade.inputs[0].default_value = .80
    links.new(variation.outputs['Color'], shade.inputs[1])
    links.new(local.outputs['Color'], shade.inputs[2])
    links.new(shade.outputs['Color'], shader.inputs['Color'])
    shader.inputs['Roughness'].default_value = .31
    shader.inputs['Radial Roughness'].default_value = .36
    links.new(shader.outputs['BSDF'], nodes['Material Output'].inputs['Surface'])
    return material


def add_fibers(name, fibers, material, bone='head', surface_name='Combed beard'):
    positions, widths, uv = fibers
    positions = np.asarray(positions, dtype=np.float32)
    positions *= np.asarray(HEAD_SCALE, dtype=np.float32)
    positions[:, :, 2] = head_height(positions[:, :, 2])
    positions[:] = fit_portrait(positions)
    part = {'Brim groom':'Fur brim', 'Pompom groom':'Pompom fibers',
            'Moustache groom':'Moustache'}.get(name)
    if part:
        positions[:] = fit_part(positions,part)
    radii = np.asarray(widths[:, None] * (.81, 1, .86, .57, .12), dtype=np.float32)
    data = bpy.data.hair_curves.new(name)
    data.add_curves([5] * len(positions))
    data.attributes['position'].data.foreach_set('vector', positions.ravel())
    radius = data.attributes.new('radius', 'FLOAT', 'POINT')
    radius.data.foreach_set('value', radii.ravel())
    shader = bpy.data.materials[surface_name].node_tree.nodes['Principled BSDF']
    tex = shader.inputs['Base Color'].links[0].from_node.image
    w,h = tex.size
    pixels = np.empty(w*h*4,dtype=np.float32)
    tex.pixels.foreach_get(pixels)
    coords = (np.asarray(uv)*(w,h)).astype(int)
    colors = pixels.reshape(h,w,4)[coords[:,1]%h,coords[:,0]%w].copy()
    attr = data.attributes.new('Groom color','FLOAT_COLOR','CURVE')
    attr.data.foreach_set('color',colors.ravel())
    data.materials.append(material)
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = bpy.data.objects['Santa_Rig']
    obj.parent_type = 'BONE'
    obj.parent_bone = bone
    bpy.context.view_layer.update()
    obj.matrix_world = Matrix.Identity(4)


def guide_grid(surface, *, normal_sign=1):
    """Sample the swept mesh and outward normals once for the whole groom."""
    rings, steps = 112, 144
    points = np.asarray([[tuple(surface(math.tau * j / rings, i / steps)) for j in range(rings)]
                         for i in range(steps + 1)], dtype=np.float64)
    across = np.roll(points, -1, axis=1) - np.roll(points, 1, axis=1)
    along = np.gradient(points, axis=0)
    normals = normal_sign * np.cross(across, along)
    normals /= np.maximum(1e-10, np.linalg.norm(normals, axis=-1, keepdims=True))
    return points, normals


def combed_fibers(rng, guides, count, angles, length, lift, roots=(.012, .965)):
    points, normals = guides
    rings = points.shape[1]
    steps = len(points) - 1
    a = rng.uniform(*angles, size=(count, 1))
    t = rng.uniform(*roots, size=(count, 1))
    s = np.linspace(0, 1, 5)[None, :]
    flyaway = rng.random((count, 1)) < .065
    advance = np.minimum(.999 - t, rng.uniform(.35, 1.28, (count, 1)) * length)
    drift = rng.uniform(-.115, .115, (count, 1)) * (1 + 1.8 * flyaway)
    sweep = (.040 * np.sin(9 * a + 21 * t) + drift) * s
    sweep += rng.uniform(-.030, .030, (count, 1)) * np.sin(s * math.pi)
    angular = (a + sweep) * (rings / math.tau) % rings
    distance = (t + advance * s) * steps
    j = angular.astype(np.intp)
    i = distance.astype(np.intp)
    next_j = (j + 1) % rings
    u, v = (angular - j)[..., None], (distance - i)[..., None]

    def interpolate(grid):
        return ((1 - v) * ((1 - u) * grid[i, j] + u * grid[i, next_j])
                + v * ((1 - u) * grid[i + 1, j] + u * grid[i + 1, next_j]))

    rise = rng.uniform(.15, 1, (count, 1)) * lift * (1 + 1.65 * flyaway)
    positions = interpolate(points) + interpolate(normals) * (rise * s ** 1.5 - .00031)[..., None]
    return positions, rng.uniform(.000038, .000096, count), np.column_stack((a[:,0]/math.tau,t[:,0]))


def fur_fibers(rng, surface, count, pompom=False):
    strands, widths, uv = [], [], []
    for _ in range(count):
        a = rng.uniform(0, math.tau)
        t = math.acos(rng.uniform(-1, 1)) / math.pi if pompom else rng.random()
        root = surface(a, t)
        if pompom:
            normal = (root - head.POMPOM).normalized()
        else:
            around = surface(a + .003, t) - root
            across = surface(a, t + .001) - root
            normal = around.cross(across).normalized()
        tuft_direction = .80 * math.sin(7 * a + 4 * t) if not pompom else .43 * math.cos(5 * a + 4 * t)
        down = Vector((tuft_direction + rng.uniform(-.68, .68), rng.uniform(-.55, .55),
                       rng.uniform(-1, .30) if pompom else rng.uniform(-1, -.48)))
        comb = (down - normal * down.dot(normal)).normalized()
        length = rng.uniform(.007, .023) * (.92 + .27 * math.cos(10 * a + 18 * t))
        if rng.random() < .14:
            length *= 1.55
        strand = []
        for i in range(5):
            s = i / 4
            strand.append(root + normal * (length * (.81 * s - .38 * s * s) - .00035)
                          + comb * (length * s * s * .96))
        strands.append(strand)
        widths.append(rng.uniform(.000068, .000193))
        uv.append((a/math.tau,t))
    return strands, np.asarray(widths), uv


def groom(draft):
    rng = np.random.default_rng(318)
    fur_rng = random.Random(318)
    white = fiber_material('Ivory beard fibers', (.35, .285, .244), (.89, .83, .77))
    fur = fiber_material('Cream hat fibers', (.46, .38, .32), (.85, .79, .75))
    density = .10 if draft else .19
    beard_guides = guide_grid(head.beard_surface, normal_sign=-1)
    for limits, strands in (((-1.63, 1.63), 69000), ((1.63, math.tau - 1.63), 41000)):
        add_fibers('Beard groom', combed_fibers(
            rng, beard_guides, int(strands * density), limits, .21, .010), white)
    add_fibers('Beard roots', combed_fibers(
        rng, beard_guides, int(17000 * density), (-1.16, 1.16), .115, .012, (.002, .18)), white)
    for part, path in head.hair_paths():
        amount = {'Moustache': 15500, 'Eyebrow': 4600, 'Temple hair': 7200, 'Temple curl': 5200}[part]
        guides = guide_grid(lambda a, t: head.lock_surface(path, a, t), normal_sign=-1)
        side = 'left' if path[len(path)//2,0]>0 else 'right'
        region = 'Nape' if part=='Temple hair' and path[len(path)//2,1]>0 else part
        add_fibers(part + ' groom', combed_fibers(
            rng, guides, int(amount * density), (-.39, math.pi + .39), .30, .0074), white,
            surface_name=region+' '+side)
    add_fibers('Brim groom', fur_fibers(fur_rng, head.brim_surface, int(65000 * density)), fur,
               surface_name='Fur brim')
    add_fibers('Pompom groom', fur_fibers(
        fur_rng, head.pompom_surface, int(23500 * density), True), fur, 'hat_tip','Pompom fibers')


def studio(scene):
    for obj in list(scene.objects):
        if obj.type == 'LIGHT' or obj.name == 'Preview_ground':
            bpy.data.objects.remove(obj, do_unlink=True)
    ambient = scene.world.node_tree.nodes['Background']
    ambient.inputs['Color'].default_value = (1, .98, .96, 1)
    ambient.inputs['Strength'].default_value = 1.46

    def softbox(name, location, energy, color, size, target=(0, -.10, 1.74)):
        data = bpy.data.lights.new(name, 'AREA')
        data.energy, data.color, data.shape, data.size = .21*energy, color, 'DISK', size
        obj = bpy.data.objects.new(name, data)
        scene.collection.objects.link(obj)
        obj.location = location
        obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()

    softbox('Warm portrait key', (.38, -.95, 2.38), 49, (1, .92, .86), .65)
    softbox('Portrait fill', (-.61, -.78, 1.81), 19, (.94, .96, 1), .82)
    softbox('Blue velvet rim', (-.77, .11, 2.04), 26, (.69, .79, 1), .61)
    softbox('Warm hair rim', (.38, .31, 2.37), 19, (1, .90, .80), .61)
    softbox('Bounce beneath the face', (-.34, -.51, 1.23), 5, (1, .93, .87), .76)

    bpy.ops.mesh.primitive_plane_add(size=2.8)
    backdrop = bpy.context.object
    backdrop.name = 'Charcoal portrait backdrop'
    material = bpy.data.materials.new('Charcoal studio gradient')
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    uv = nodes.new('ShaderNodeTexCoord')
    distance = nodes.new('ShaderNodeVectorMath')
    distance.operation = 'DISTANCE'
    distance.inputs[1].default_value = (.49, .55, 0)
    links.new(uv.outputs['UV'], distance.inputs[0])
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (.150, .143, .148, 1)
    ramp.color_ramp.elements[1].position = .37
    ramp.color_ramp.elements[1].color = (.102, .096, .101, 1)
    links.new(distance.outputs['Value'], ramp.inputs['Fac'])
    emission = nodes.new('ShaderNodeEmission')
    emission.inputs['Strength'].default_value = .52
    links.new(ramp.outputs['Color'], emission.inputs['Color'])
    links.new(emission.outputs[0], nodes['Material Output'].inputs['Surface'])
    backdrop.data.materials.append(material)
    scene.render.film_transparent = False
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0
    return backdrop


def frame_portrait(camera, backdrop, view):
    location, center, roll, lens = CAMERAS[view]
    camera.location = location
    target = Vector(center)
    if view == 'side':
        pivot = Matrix.Translation((0, -.04, 1.75))
        rotate = pivot @ Matrix.Rotation(math.radians(-68), 4, 'Z') @ pivot.inverted()
        for obj in bpy.context.scene.objects:
            if obj.type == 'LIGHT':
                obj.matrix_world = rotate @ obj.matrix_world
    else:
        target.z += .006
    direction = target - camera.location
    aim = direction.to_track_quat('-Z', 'Y')
    camera.rotation_euler = (aim @ Quaternion((0, 0, 1), math.radians(roll))).to_euler()
    camera.data.lens_unit = 'MILLIMETERS'
    camera.data.lens = lens * .980
    backdrop.location = target + direction.normalized() * .66
    backdrop.rotation_euler = (-direction).to_track_quat('Z', 'Y').to_euler()


def shade_undercoat():
    """Keep the groom visibly distinct from the meshes beneath its strands."""
    for material_name, tint, relief in (
        (head.model.HAIR, (.62, .54, .48, 1), .56),
        (head.model.FUR, (.72, .64, .59, 1), .71),
    ):
        tree = bpy.data.materials[material_name].node_tree
        nodes, links = tree.nodes, tree.links
        shader = nodes['Principled BSDF']
        color = shader.inputs['Base Color']
        tint_node = nodes.new('ShaderNodeMixRGB')
        tint_node.label = 'Warm shadow beneath the groom'
        tint_node.blend_type = 'MULTIPLY'
        tint_node.inputs[0].default_value = 1
        tint_node.inputs[2].default_value = tint
        links.new(color.links[0].from_socket, tint_node.inputs[1])
        links.new(tint_node.outputs[0], color)
        shader.inputs['Sheen Weight'].default_value *= .65
        nodes['Normal Map'].inputs['Strength'].default_value = relief


def main():
    options = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    if set(options) - {'draft', 'both'}:
        raise ValueError('Expected the optional arguments draft and both')
    draft = 'draft' in options
    scene = bpy.context.scene
    scene.name = 'Santa Head Portrait'
    keep_head(bpy.data.objects['Santa'])
    groom(draft)
    shade_undercoat()
    backdrop = studio(scene)
    bpy.ops.object.select_all(action='DESELECT')
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.region_3d.view_perspective = 'CAMERA'
                area.spaces.active.overlay.show_overlays = False
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 14 if draft else 40
    scene.cycles.adaptive_threshold = .07 if draft else .025
    scene.cycles.use_denoising = True
    scene.render.resolution_x = scene.render.resolution_y = 520 if draft else 1080
    folder = ROOT / ('generated' if draft else 'previews')
    scene.render.image_settings.color_mode = 'RGB'
    for view in ('front', 'side') if 'both' in options else ('front',):
        frame_portrait(scene.camera, backdrop, view)
        name = 'santa-head-draft' if draft else 'santa-head-portrait'
        name += '-side' if view == 'side' else ''
        scene.render.image_settings.file_format = 'PNG'
        scene.render.filepath = str(folder / f'{name}.png')
        if not draft and view == 'front':
            bpy.context.preferences.filepaths.save_version = 0
            bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / 'generated' / f'{name}.blend'), compress=True)
        bpy.ops.render.render(write_still=True)
        if not draft:
            scene.render.image_settings.file_format = 'WEBP'
            scene.render.image_settings.quality = 90
            bpy.data.images['Render Result'].save_render(str(ROOT / 'docs' / f'{name}.webp'), scene=scene)


if __name__ == '__main__':
    main()
