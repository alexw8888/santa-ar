"""Score a head portrait render against the front and side reference photographs.

blender -b -t 4 --factory-startup --python-exit-code 1 -P tests/compare_head_portrait.py -- FOLDER

FOLDER holds front.png and side.png from render_santa_head.py (draft or full size). The
portrait cameras are registered to the references, so both images are compared in the same
frame after resampling to 512 px; no per-image alignment is applied. The script writes
FOLDER/compare-front.png and compare-side.png (reference | render | difference) and
FOLDER/eyes.png (reference and render eye crops at 4x), and prints and saves scores.json:

- silhouette: intersection over union of the head masks found against the charcoal backdrop.
- structure: mean SSIM of luminance over the union of the masks, at 256 and 128 px
  (fine and coarse structure).
- color: 1 - mean CIELAB distance / 100 over the union, after a light blur so fibre-level
  texture is not counted as a color difference.
- similarity: the mean of the three, per view; the headline is the mean over both views.
Regions (eyes, nose, mouth, cap, beard) repeat structure and color inside fixed boxes in the
reference frame so a local change such as the irises can be tracked on its own.
"""
from collections import deque
import json
from pathlib import Path
import struct
import sys
import zlib

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SIZE = 512
# Boxes in the 512 px reference frame: x0, y0, x1, y1.
REGIONS = {
    'front': {
        'eyes': (175, 180, 375, 225),
        'nose': (240, 205, 330, 275),
        'mouth': (215, 270, 355, 345),
        'cap': (40, 0, 400, 140),
        'beard': (100, 330, 470, 505),
        'face': (150, 130, 400, 350),
    },
    'side': {
        'eyes': (330, 175, 430, 225),
        'nose': (380, 215, 440, 270),
        'mouth': (350, 270, 425, 330),
        'cap': (20, 0, 400, 180),
        'beard': (100, 280, 460, 500),
        'face': (280, 140, 440, 340),
    },
}
EYE_BOXES = {'front': [(195, 185, 255, 225), (295, 175, 355, 215)],
             'side': [(320, 170, 400, 220)]}


def read_image(path):
    image = bpy.data.images.load(str(Path(path).resolve()), check_existing=False)
    image.colorspace_settings.name = 'Non-Color'
    width, height = image.size
    pixels = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(pixels)
    bpy.data.images.remove(image)
    return np.clip(pixels.reshape(height, width, 4)[::-1, :, :3], 0, 1).astype(np.float64)


def resample(pixels, size):
    """Area-average (or bilinear when enlarging) to a square of the given size."""
    height, width = pixels.shape[:2]
    if height % size == 0 and width % size == 0:
        f = height // size
        return pixels.reshape(size, f, size, f, -1).mean(axis=(1, 3))
    # Box-filter through an integral image, then sample cell averages.
    edges_y = np.linspace(0, height, size + 1)
    edges_x = np.linspace(0, width, size + 1)
    if height < size:
        y = np.clip((np.arange(size) + .5) * height / size - .5, 0, height - 1)
        x = np.clip((np.arange(size) + .5) * width / size - .5, 0, width - 1)
        y0, x0 = np.floor(y).astype(int), np.floor(x).astype(int)
        y1, x1 = np.minimum(y0 + 1, height - 1), np.minimum(x0 + 1, width - 1)
        fy, fx = (y - y0)[:, None, None], (x - x0)[None, :, None]
        return ((1 - fy) * ((1 - fx) * pixels[y0][:, x0] + fx * pixels[y0][:, x1])
                + fy * ((1 - fx) * pixels[y1][:, x0] + fx * pixels[y1][:, x1]))
    integral = np.zeros((height + 1, width + 1, pixels.shape[2]))
    integral[1:, 1:] = pixels.cumsum(0).cumsum(1)

    def lookup(ys, xs):
        y0, x0 = np.floor(ys).astype(int), np.floor(xs).astype(int)
        return integral[y0][:, x0]

    total = (lookup(edges_y[1:], edges_x[1:]) - lookup(edges_y[:-1], edges_x[1:])
             - lookup(edges_y[1:], edges_x[:-1]) + lookup(edges_y[:-1], edges_x[:-1]))
    area = (np.floor(edges_y[1:]) - np.floor(edges_y[:-1]))[:, None, None] * \
           (np.floor(edges_x[1:]) - np.floor(edges_x[:-1]))[None, :, None]
    return total / area


def blur(values, sigma):
    radius = int(3 * sigma + .5)
    kernel = np.exp(-.5 * (np.arange(-radius, radius + 1) / sigma) ** 2)
    kernel /= kernel.sum()
    out = values
    for axis in (0, 1):
        padded = np.pad(out, [(radius, radius) if a == axis else (0, 0) for a in range(out.ndim)], mode='edge')
        acc = np.zeros_like(out)
        for i, k in enumerate(kernel):
            acc += k * np.take(padded, range(i, i + out.shape[axis]), axis=axis)
        out = acc
    return out


def flood(region, y, x):
    height, width = region.shape
    stride = width + 2
    padded = bytearray(np.pad(region, 1).astype('uint8').tobytes())
    found = bytearray(len(padded))
    first = (y + 1) * stride + x + 1
    pending = deque([first])
    padded[first] = 0
    while pending:
        index = pending.popleft()
        found[index] = 1
        for adjacent in (index - stride, index - 1, index + 1, index + stride):
            if padded[adjacent]:
                padded[adjacent] = 0
                pending.append(adjacent)
    return np.frombuffer(found, dtype='uint8').reshape(height + 2, stride)[1:-1, 1:-1].astype(bool)


def silhouette(rgb):
    corner = SIZE // 12
    corners = np.concatenate([rgb[y:y + corner, x:x + corner].reshape(-1, 3)
                              for y in (0, SIZE - corner) for x in (0, SIZE - corner)])
    background = np.median(corners, axis=0)
    peak, low = rgb.max(axis=2), rgb.min(axis=2)
    candidate = (peak > background.max() + .077) | (peak - low > np.ptp(background) + .048)
    points = np.argwhere(candidate)
    y, x = points[np.argmin(np.sum((points - SIZE / 2) ** 2, axis=1))]
    foreground = flood(candidate, int(y), int(x))
    surrounded = np.pad(~foreground, 1, constant_values=True)
    return ~flood(surrounded, 0, 0)[1:-1, 1:-1]


def lab(rgb):
    linear = np.where(rgb <= .04045, rgb / 12.92, ((rgb + .055) / 1.055) ** 2.4)
    xyz = linear @ np.array([[.4124, .3576, .1805], [.2126, .7152, .0722], [.0193, .1192, .9505]]).T
    xyz /= (.95047, 1, 1.08883)
    f = np.where(xyz > .008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack((116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])), -1)


def luminance(rgb):
    return rgb @ np.array((.2126, .7152, .0722))


def ssim_map(a, b, sigma=1.5):
    c1, c2 = .01 ** 2, .03 ** 2
    mu_a, mu_b = blur(a, sigma), blur(b, sigma)
    var_a = blur(a * a, sigma) - mu_a ** 2
    var_b = blur(b * b, sigma) - mu_b ** 2
    cov = blur(a * b, sigma) - mu_a * mu_b
    return ((2 * mu_a * mu_b + c1) * (2 * cov + c2)) / ((mu_a ** 2 + mu_b ** 2 + c1) * (var_a + var_b + c2))


def structure(reference, render, mask, box=None, sizes=(256, 128)):
    scores = []
    for size in sizes:
        f = SIZE // size
        a = luminance(resample(reference, size))
        b = luminance(resample(render, size))
        m = resample(mask[..., None].astype(float), size)[..., 0] > .5
        s = ssim_map(a, b)
        if box:
            x0, y0, x1, y1 = (v // f for v in box)
            region = np.zeros_like(m)
            region[y0:y1, x0:x1] = True
            m = region
        scores.append(float(s[m].mean()))
    return float(np.mean(scores))


def color(reference, render, mask, box=None):
    a, b = lab(blur(reference, 1.2)), lab(blur(render, 1.2))
    distance = np.linalg.norm(a - b, axis=-1)
    if box:
        x0, y0, x1, y1 = box
        region = np.zeros_like(mask)
        region[y0:y1, x0:x1] = True
        mask = region
    return float(max(0, 1 - distance[mask].mean() / 100))


def write_png(path, rgb):
    height, width = rgb.shape[:2]
    pixels = np.uint8(np.round(np.clip(rgb, 0, 1) * 255))

    def chunk(name, data):
        body = name + data
        return struct.pack('!I', len(data)) + body + struct.pack('!I', zlib.crc32(body))

    rows = b''.join(b'\0' + row.tobytes() for row in pixels)
    Path(path).write_bytes(b'\x89PNG\r\n\x1a\n'
                           + chunk(b'IHDR', struct.pack('!2I5B', width, height, 8, 2, 0, 0, 0))
                           + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))


def crop(image, box, zoom, full):
    """Crop a box given in the 512 frame from a full-resolution image, enlarged by zoom."""
    x0, y0, x1, y1 = box
    height = full.shape[0]
    s = height / SIZE
    piece = full[int(y0 * s):int(y1 * s), int(x0 * s):int(x1 * s)]
    target_h, target_w = (y1 - y0) * zoom, (x1 - x0) * zoom
    ys = np.clip(((np.arange(target_h) + .5) * piece.shape[0] / target_h).astype(int), 0, piece.shape[0] - 1)
    xs = np.clip(((np.arange(target_w) + .5) * piece.shape[1] / target_w).astype(int), 0, piece.shape[1] - 1)
    return piece[ys][:, xs]


def main():
    folder = Path(sys.argv[sys.argv.index('--') + 1])
    report = {}
    eye_rows = []
    for view, photo in (('front', 'head.png'), ('side', 'side.png')):
        reference_full = read_image(ROOT / 'photos' / photo)
        render_full = read_image(folder / f'{view}.png')
        reference, render = resample(reference_full, SIZE), resample(render_full, SIZE)
        ref_mask, render_mask = silhouette(reference), silhouette(render)
        union = ref_mask | render_mask
        scores = {
            'silhouette': float((ref_mask & render_mask).sum() / union.sum()),
            'structure': structure(reference, render, union),
            'color': color(reference, render, union),
        }
        scores['similarity'] = float(np.mean(list(scores.values())))
        scores['structure_by_size'] = {size: round(structure(reference, render, union, sizes=(size,)), 4)
                                       for size in (256, 128, 64, 32)}
        scores['regions'] = {name: {'structure': round(structure(reference, render, union, box), 4),
                                    'color': round(color(reference, render, union, box), 4)}
                             for name, box in REGIONS[view].items()}
        report[view] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in scores.items()}
        difference = np.linalg.norm(lab(blur(reference, 1.2)) - lab(blur(render, 1.2)), axis=-1) / 40
        heat = np.stack((np.clip(difference, 0, 1), np.clip(difference - .5, 0, 1) * 2, .15 + 0 * difference), -1)
        gap = np.full((SIZE, 6, 3), .1)
        write_png(folder / f'compare-{view}.png', np.concatenate((reference, gap, render, gap, heat), 1))
        for box in EYE_BOXES[view]:
            pair = [crop(None, box, 4, reference_full), crop(None, box, 4, render_full)]
            eye_rows.append(np.concatenate((pair[0], np.full((pair[0].shape[0], 6, 3), .1), pair[1]), 1))
    width = max(r.shape[1] for r in eye_rows)
    rows = []
    for r in eye_rows:
        rows.append(np.pad(r, ((0, 6), (0, width - r.shape[1]), (0, 0)), constant_values=.1))
    write_png(folder / 'eyes.png', np.concatenate(rows, 0))
    report['similarity'] = round(float(np.mean([report[v]['similarity'] for v in ('front', 'side')])), 4)
    text = json.dumps(report, indent=1)
    (folder / 'scores.json').write_text(text + '\n')
    print(text)


if __name__ == '__main__':
    main()
