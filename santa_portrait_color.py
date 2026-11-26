"""Bake the two registered photographs onto fixed UVs on the sculpted surfaces."""
from functools import lru_cache
from pathlib import Path

import bpy
import numpy as np

import santa_model as model
import santa_portrait_fit as fit


@lru_cache(None)
def reference(view):
    filename = 'head.png' if view == 'front' else 'side.png'
    rgb = read_pixels(Path(model.HERE, 'photos', filename))
    gain = read_pixels(Path(model.HERE,'assets','textures',f'santa-head-{view}-diffuse-fit.png'))
    h,w = rgb.shape[:2]
    x = np.linspace(0,gain.shape[1]-1,w).astype(int)
    y = np.linspace(0,gain.shape[0]-1,h).astype(int)
    return np.clip(rgb*np.exp(1.22*(gain[y[:,None],x]-.5)),0,1)


def read_pixels(path):
    im = bpy.data.images.load(str(path), check_existing=False)
    im.colorspace_settings.name = 'Non-Color'
    w, h = im.size
    pixels = np.empty(w*h*4, dtype=np.float32)
    im.pixels.foreach_get(pixels)
    bpy.data.images.remove(im)
    return pixels.reshape(h, w, 4)[::-1, :, :3].copy()


def polygon_mask(px, py, outline):
    inside = np.zeros(px.shape, dtype=bool)
    for (x,y),(xx,yy) in zip(outline, outline[1:]+outline[:1]):
        if y != yy:
            inside ^= ((py>y) != (py>yy)) & (px < x+(py-y)*(xx-x)/(yy-y))
    return inside


@lru_cache(None)
def donor(view, family):
    rgb = reference(view)
    h,w = rgb.shape[:2]
    py,px = np.mgrid[:h,:w].astype(np.float32)
    px *= 520/w
    py *= 520/h
    r,g,b = np.moveaxis(rgb,2,0)
    if family == 'velvet':
        valid = np.clip((r - 1.65*np.maximum(g,b) - .045)*12, 0, 1)
    elif family == 'skin':
        valid = np.clip((r-g-.075)*16, 0, 1) * np.clip((g-b-.019)*23, 0, 1)
        valid *= np.clip((g-.13)*10, 0, 1)
        # Exclude the rims, pads, temples, eyebrows and eyes from the skin projection.
        # The animated eyes and the wire frames carry their own materials.
        if view == 'front':
            valid *= polygon_mask(px,py,[(155,207),(174,165),(226,145),(311,127),(349,130),
                (374,148),(393,206),(407,266),(387,292),(332,267),(292,277),(249,274),
                (213,295),(177,297),(156,275)])
            for cx,cy,rx,ry in [(226,238,38,23),(342,220,38,23)]:
                xx, yy = px-cx, py-cy+.14*(px-cx)
                rr = np.sqrt((xx/rx)**2 + (yy/ry)**2)
                valid *= np.clip((np.abs(rr-1)-.12)*6,0,1)
            valid *= np.where((px>249)&(px<317)&(py>207)&(py<234),0,1)
            valid *= np.where((px<203)&(py>217)&(py<243),0,1)
            valid *= np.where((px>365)&(py>193)&(py<215),0,1)
            valid *= np.where(((px-225)/28)**2+((py-211)/10)**2 < 1,0,1)
            valid *= np.where(((px-325)/29)**2+((py-195)/10)**2 < 1,0,1)
            valid *= np.where(py<139,0,1)
        else:
            valid *= polygon_mask(px,py,[(271,201),(303,174),(318,148),(359,134),
                (381,153),(389,193),(410,211),(435,229),(435,249),(409,267),
                (371,264),(342,286),(293,294),(261,269)])
            valid *= np.where((px>225)&(py>203)&(py<224),0,1)
            valid *= np.where((px>366)&(py>185)&(py<248),0,1)
            valid *= np.where(((px-354)/22)**2+((py-194)/11)**2 < 1,0,1)
    elif family in ('cavity', 'lip', 'tongue', 'ear'):
        outlines = {
            'cavity': ([(246,323),(273,317),(312,314),(343,305),(340,321),(325,336),(300,342),(270,337)],
                       [(366,308),(386,302),(401,309),(409,325),(395,327),(379,319)]),
            'lip': ([(240,325),(261,336),(280,341),(307,341),(330,332),(346,310),
                     (350,313),(341,336),(323,349),(298,356),(271,352),(249,342)],
                    [(369,314),(395,328),(408,325),(412,320),(419,333),(411,340),(395,336),(377,325)]),
            'tongue': ([(266,335),(276,329),(293,325),(308,324),(325,321),(331,326),(316,337),(293,340)],
                       [(379,316),(386,311),(399,317),(407,324),(398,327)]),
            'ear': ([],[(181,233),(195,225),(211,230),(222,246),(216,272),(204,287),(190,275),(181,257)]),
        }
        region = outlines[family][view == 'side']
        valid = polygon_mask(px,py,region).astype(np.float32)
        if family == 'cavity':
            valid *= np.clip((.58-g)*9,0,1)
        elif family == 'lip':
            valid *= np.clip((r-g-.105)*9,0,1)
    else:
        valid = np.clip((.225-(r-g))*15, 0, 1) * np.clip((b-.34)*9, 0, 1)
    # Pull valid pixels down a pyramid and push the interpolated values back into
    # holes. This extends skin under the wires and pile beyond the edge of the hat.
    levels = []
    color, weight = rgb, valid.astype(np.float32)
    while min(color.shape[:2]) > 2:
        levels.append((color,weight))
        nh,nw = weight.shape
        packed = np.dstack((color*weight[...,None], weight))
        padded = np.pad(packed, ((0,nh%2),(0,nw%2),(0,0)), mode='edge')
        small = (padded[::2,::2]+padded[1::2,::2]+padded[::2,1::2]+padded[1::2,1::2])*.25
        weight = small[...,3]
        color = small[...,:3] / np.maximum(weight[...,None],1e-10)
    for original, weight in reversed(levels):
        up = np.repeat(np.repeat(color,2,axis=0),2,axis=1)
        pad = np.pad(up, ((1,1),(1,1),(0,0)), mode='edge')
        up = (4*up + pad[1:-1,:-2] + pad[1:-1,2:] + pad[2:,1:-1] + pad[:-2,1:-1])*.125
        color = original*weight[...,None] + up[:weight.shape[0],:weight.shape[1]]*(1-weight[...,None])
    return color


def sample_photo(points, view, family):
    uv = fit.project(points, view)
    uv += fit.offsets(uv, view, texture=True)
    raster = donor(view, family)
    h, w = raster.shape[:2]
    p = np.clip(uv / 520, 0, .999) * (w-1, h-1)
    x, y = p.astype(int).T
    u, v = (p - p.astype(int)).T[:, :, None]
    return ((1-v)*((1-u)*raster[y,x] + u*raster[y,x+1])
            + v*((1-u)*raster[y+1,x] + u*raster[y+1,x+1]))


def photograph(grid, size, family, fallback):
    """Interpolate the loft in 3D before projecting each texture sample into both photos."""
    width, height = size
    grid = np.array(grid, dtype=np.float64)
    grid[..., 0] *= model.HEAD_SCALE.x
    grid[..., 1] *= model.HEAD_SCALE.y
    grid[..., 2] = model.head_height(grid[..., 2])
    grid = fit.fit(grid, texture_grid=True)
    last_y, last_x = np.array(grid.shape[:2])-1
    # A PNG's first row is UV V=1.
    uu = (np.arange(width)+.5)*last_x/width
    vv = (1-(np.arange(height)+.5)/height)*last_y
    x, fu = uu.astype(int), (uu % 1)[None,:,None]
    image = np.empty((height,width,3), dtype=np.float32)
    for start in range(0, height, 24):
        v = vv[start:start+24, None]
        y = v.astype(int)
        fv = (v % 1)[...,None]
        across = grid[y,x+1]-grid[y,x]
        along = grid[y+1,x]-grid[y,x]
        points = ((1-fv)*(grid[y,x]+fu*across)
                  + fv*((1-fu)*grid[y+1,x]+fu*grid[y+1,x+1])).reshape(-1,3)
        normals = np.cross(across,along).reshape(-1,3)
        frontal = np.abs(normals[:,1])
        lateral = np.abs(normals[:,0])
        # Prefer the side view around the temples and the back of the beard.
        side_mix = lateral**3 / np.maximum(1e-25, lateral**3 + 1.6*frontal**3)
        side_mix = np.maximum(side_mix, np.clip((points[:,1]+.035)*5, 0, .84))
        if family == 'beard':
            facing = np.cos((np.arange(width)+.5)*2*np.pi/width)
            side_mix = np.broadcast_to(np.clip((.91-facing)/.69,0,1),
                                       (len(v), width)).reshape(-1).copy()
        mirrored = points.copy()
        mirrored[:,0] = -np.abs(mirrored[:,0])
        if family == 'skin':
            side_mix = np.clip((np.abs(points[:,0])-.085)/.118,0,1)
        elif family == 'ear':
            side_mix[:] = 1
        elif family in ('cavity','tongue','lip'):
            side_mix *= np.clip(np.abs(points[:,0])/.10,0,.65)
        front = sample_photo(points, 'front', family)
        side = sample_photo(mirrored, 'side', family)
        rgb = front*(1-side_mix[:,None]) + side*side_mix[:,None]
        if family == 'skin':
            base = fallback[start:start+len(v)].reshape(-1,3)
            rgb = .92*rgb + .08*base
        # Convert the photographed colors to diffuse reflectance for studio and AR lighting.
        linear = np.where(rgb <= .04045, rgb/12.92, ((rgb+.055)/1.055)**2.4)
        gain = {'hair': .51, 'beard': .54, 'velvet': .54, 'skin': .55,
                'lip': .58, 'tongue': .90, 'cavity': .82, 'ear': .60}[family]
        image[start:start+len(v)] = model.to_srgb(linear*gain).reshape(len(v), width, 3)
    return image


def painted_material(base, name, grid, size, family):
    fallback = np.array((.64,.044,.064) if family == 'velvet' else (.82,.77,.71))
    if family == 'skin':
        source = bpy.data.images['Santa_rosy_cheeks']
        w,h = source.size
        colors = np.empty(w*h*4, dtype=np.float32)
        source.pixels.foreach_get(colors)
        fallback = model.to_srgb(colors.reshape(h,w,4)[::-1,:,:3])
    rgb = photograph(grid, size, family, fallback)
    corrections = surface_corrections()
    if name in corrections:
        gain = corrections[name]
        h,w = rgb.shape[:2]
        yy = np.linspace(0,gain.shape[0]-1,h)
        xx = np.linspace(0,gain.shape[1]-1,w)
        y,x = np.minimum(yy.astype(int),gain.shape[0]-2),np.minimum(xx.astype(int),gain.shape[1]-2)
        u,v = (xx-x)[None,:,None],(yy-y)[:,None,None]
        gain = ((1-v)*((1-u)*gain[y[:,None],x]+u*gain[y[:,None],x+1])
                + v*((1-u)*gain[y[:,None]+1,x]+u*gain[y[:,None]+1,x+1]))
        linear = np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4)
        rgb = model.to_srgb(linear*np.exp((gain-128)/75))
    if family == 'skin':
        rgb = clear_skin(rgb)
    elif family in ('hair', 'beard'):
        rgb = clean_white(rgb)
    image = model.image_file(name.replace(' ', '_')+'_color', rgb)
    material = bpy.data.materials[base] if name == base else bpy.data.materials[base].copy()
    material.name = name
    material['head_surface'] = base
    tree = material.node_tree
    tex = tree.nodes.new('ShaderNodeTexImage')
    tex.image = image
    tree.links.new(tex.outputs['Color'], tree.nodes['Principled BSDF'].inputs['Base Color'])
    if family in ('hair','beard','velvet'):
        shader = tree.nodes['Principled BSDF']
        shader.inputs['Sheen Weight'].default_value = .045
        shader.inputs['Specular IOR Level'].default_value = .17
        tree.nodes['Normal Map'].inputs['Strength'].default_value *= .30
        if family == 'velvet':
            # Deep, saturated scarlet as in the references: the photographed pile already
            # carries its highlights, so a white specular layer only turns it pink.
            shader.inputs['Sheen Weight'].default_value = 0
            shader.inputs['Specular IOR Level'].default_value = .06
    if name != base:
        model.MATS.append(material)
    return material.name


def rank_filter(values, size, reduce):
    """Separable square max or min filter."""
    pad = size // 2
    for axis in (0, 1):
        widths = [(pad, pad) if a == axis else (0, 0) for a in range(values.ndim)]
        padded = np.pad(values, widths, mode='edge')
        values = reduce(np.lib.stride_tricks.sliding_window_view(padded, size, axis=axis), axis=-1)
    return values


def soften(values, sigma):
    radius = int(3 * sigma + .5)
    kernel = np.exp(-.5 * (np.arange(-radius, radius + 1) / sigma) ** 2)
    kernel /= kernel.sum()
    for axis in (0, 1):
        widths = [(radius, radius) if a == axis else (0, 0) for a in range(values.ndim)]
        padded = np.pad(values, widths, mode='edge')
        values = sum(k * np.take(padded, range(i, i + values.shape[axis]), axis=axis)
                     for i, k in enumerate(kernel))
    return values


def clear_skin(rgb):
    """Remove thin dark marks the photographs leave on the skin chart.

    Spectacle rims, lashes and stray eyebrow hairs land on the skin wherever the sculpt and
    the photograph disagree by a few pixels, and read as dirty smudges. A grey closing (max
    then min) removes dark features narrower than its window while keeping the broad rosy
    colouring; the fine relief comes from the skin's normal map instead.
    """
    rgb = np.asarray(rgb, dtype=np.float32)
    closed = rank_filter(rank_filter(rgb, 15, np.max), 15, np.min)
    return np.clip(soften(closed, 2.2), 0, 1)


def clean_white(rgb, keep=.30):
    """Keep the photographed strand shading of white hair and fur, without its stains.

    Where a lock or the brim and the photograph disagree, the projection picks up pink
    skin, the brown of shadowed curls and the charcoal backdrop, and the white hair reads
    grey-brown. Keep each chart's light and dark pattern and its mean brightness, drop
    most of its local colour, and lift the backdrop's deep leaks to a soft shadow.
    """
    rgb = np.asarray(rgb, dtype=np.float32)
    weights = np.array((.2126, .7152, .0722), dtype=np.float32)
    lum = rgb @ weights
    # Keep the shadowed gaps between curls; lift only the backdrop's near-black leaks.
    lum = np.clip(lum, .42 * np.median(lum), np.percentile(lum, 99.7))
    # The references' white hair is a warm cream on average; keep each chart's mean tint.
    tint = rgb.reshape(-1, 3).mean(0)
    white = lum[..., None] * tint / (tint @ weights)
    return np.clip(white * (1 - keep) + rgb * keep, 0, 1)


@lru_cache(None)
def surface_corrections():
    path = Path(model.HERE,'assets','textures','santa-head-surface-fit.npz')
    if not path.exists():
        return {}
    with np.load(path) as maps:
        return {name:maps[name].astype(np.float32) for name in maps.files}
