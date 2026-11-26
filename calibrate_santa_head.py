"""Fit diffuse textures from two actual Blender renders and their UV visibility passes.

blender -b santa_base.blend -P calibrate_santa_head.py -- generated/refine-09
The directory contains front.png and side.png rendered with the portrait cameras.
"""
import sys
from pathlib import Path

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import render_santa_head as portrait
from santa_portrait_color import read_pixels


def blur(values, radius):
    h,w = values.shape[:2]
    fy,fx = np.fft.fftfreq(h)[:,None],np.fft.fftfreq(w)[None,:]
    kernel = np.exp(-2*np.pi**2*radius**2*(fy**2+fx**2))
    return np.fft.ifft2(np.fft.fft2(values, axes=(0,1))*kernel[...,None],axes=(0,1)).real


def head_bounds(rgb):
    h,w = rgb.shape[:2]
    bg = np.median(rgb[:h//14,:w//14].reshape(-1,3),axis=0)
    foreground = ((rgb.max(axis=2)>bg.max()+.08)|(np.ptp(rgb,axis=2)>np.ptp(bg)+.055))
    y,x = np.nonzero(foreground)
    return np.array([(x.min()+x.max())/2,(y.min()+y.max())/2]),max(x.max()-x.min(),y.max()-y.min())


def uv_pass(scene, folder, view, size):
    scene.render.resolution_x = scene.render.resolution_y = size
    scene.render.image_settings.file_format = 'OPEN_EXR'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.film_transparent = True
    scene.render.filepath = str(folder/f'{view}-uv.exr')
    scene.cycles.samples = 1
    scene.cycles.use_denoising = False
    scene.cycles.filter_width = .01
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(scene.render.filepath,check_existing=False)
    data = np.empty(size*size*4, dtype=np.float32)
    im.pixels.foreach_get(data)
    bpy.data.images.remove(im)
    return data.reshape(size,size,4)[::-1].copy()


def main():
    folder = Path(sys.argv[sys.argv.index('--')+1]).resolve()
    mesh = bpy.data.objects['Santa']
    portrait.keep_head(mesh)
    scene = bpy.context.scene
    backdrop = portrait.studio(scene)
    backdrop.hide_render = True
    surfaces = {}
    for index, mat in enumerate(list(mesh.data.materials)):
        if 'head_surface' in mat:
            bs = mat.node_tree.nodes['Principled BSDF']
            image = bs.inputs['Base Color'].links[0].from_node.image
            w,h = image.size
            surfaces[index+1] = (mat.name, max(80,min(700, w//2)), max(64,min(520,h//2)))
        marker = bpy.data.materials.new(f'UV pass {index}')
        tree = marker.node_tree
        coord = tree.nodes.new('ShaderNodeTexCoord')
        xyz = tree.nodes.new('ShaderNodeSeparateXYZ')
        pack = tree.nodes.new('ShaderNodeCombineXYZ')
        emit = tree.nodes.new('ShaderNodeEmission')
        tree.links.new(coord.outputs['UV'],xyz.inputs[0])
        for axis in ('X','Y'):
            tree.links.new(xyz.outputs[axis],pack.inputs[axis])
        pack.inputs['Z'].default_value = (index+1)/64
        tree.links.new(pack.outputs[0],emit.inputs[0])
        tree.links.new(emit.outputs[0],tree.nodes['Material Output'].inputs['Surface'])
        mesh.data.materials[index] = marker
    accum = {name:np.zeros((h,w,4)) for name,w,h in surfaces.values()}
    for view,filename in [('front','head.png'),('side','side.png')]:
        actual = read_pixels(folder/(view+'.png'))
        size = actual.shape[0]
        source = read_pixels(ROOT/'photos'/filename)
        p,extent = head_bounds(source)
        q,render_extent = head_bounds(actual)
        coords = (np.arange(size)[:,None]-q)*extent/render_extent+p
        x,y = np.clip(coords,0,len(source)-1).astype(int).T
        target = source[y[:,None],x]
        portrait.frame_portrait(scene.camera,backdrop,view)
        uv = uv_pass(scene,folder,view,size)
        ids = np.rint(uv[:,:,2]*64).astype(int)
        delta = np.clip(2.05*(np.log(.043+target)-np.log(.043+actual)),-1.15,1.15)
        r,g,b = np.moveaxis(target,2,0)
        for index,(name,w,h) in surfaces.items():
            visible = (ids==index)&(uv[:,:,3]>.98)
            if name == 'Folded velvet':
                visible &= (r>1.65*np.maximum(g,b))&(r-g>.11)
            elif name in ('Laughing_face_skin','Ear left','Ear right','Warm_lips'):
                visible &= (r-g>.115)&(g-b>.022)&(g>.16)
                # Omit wire highlights and deep edges adjoining the eyelids or mouth.
                edge = np.maximum(np.abs(np.gradient(g,axis=0)),np.abs(np.gradient(g,axis=1)))
                visible &= edge<.055
            elif name in ('Tongue','Laughing_mouth'):
                visible &= (r>1.2*g)&(g<.50)
            else:
                visible &= (r-g < .23)&(b>.32)
            u,v = uv[visible,:2].T
            x = np.clip((u*w).astype(int),0,w-1)
            y = np.clip(((1-v)*h).astype(int),0,h-1)
            idx = y*w+x
            d = delta[visible]
            bins = accum[name].reshape(-1,4)
            for c in range(3):
                bins[:,c] += np.bincount(idx,weights=d[:,c],minlength=w*h)
            bins[:,3] += np.bincount(idx,minlength=w*h)
    output = ROOT/'assets/textures/santa-head-surface-fit.npz'
    previous = dict(np.load(output)) if output.exists() else {}
    result = {}
    for name, data in accum.items():
        local = blur(data,1.3)
        coarse = blur(data,7.0)
        prior = coarse[:,:,:3]/np.maximum(coarse[:,:,3:],.01)
        d = (local[:,:,:3]+.08*prior) / np.maximum(.08+local[:,:,3:],.08)
        d = np.clip(d,-.98,.98)
        if name in previous:
            d += (previous[name].astype(float)-128)/75
        result[name] = np.uint8(np.clip(np.round(128+75*d),0,255))
    np.savez_compressed(output,**result)


if __name__ == '__main__':
    main()
