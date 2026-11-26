"""Two-view registration of the head sculpt and its photographic texture samples."""
import math
from functools import lru_cache

import numpy as np
from mathutils import Quaternion, Vector


# Rest-pose sculpt landmarks and the corresponding reference pixels on a 520px square.
# Rings trace the cap, brim, cheek, beard and pom. Interior landmarks locate facial features.
FRONT = [
    (223,3,211,3),(147,15,152,15),(81,61,107,65),(48,137,43,145),
    (46,220,32,223),(52,262,39,267),(89,260,83,264),(121,179,98,180),
    (150,107,136,123),(220,64,200,73),(332,34,335,39),
    (403,55,397,60),(445,98,432,114),(428,144,438,158),
    (394,135,395,146),(329,116,328,129),(265,130,253,141),
    (175,204,156,207),(121,232,103,233),
    (19,304,9,312),(68,350,60,359),(121,310,114,312),
    (147,292,130,283),(110,348,91,350),(104,422,115,427),
    (168,467,173,466),(284,491,275,509),(386,473,379,476),
    (452,440,443,433),(500,386,467,396),(508,348,475,351),
    (466,291,453,287),(447,243,447,242),
    (245,208,225,211),(338,197,325,196),(257,165,243,173),
    (325,156,322,154),(186,230,185,235),(272,234,264,235),
    (313,221,306,219),(397,212,377,211),
    (299,258,290,256),(265,272,251,269),(327,262,324,265),
    (187,279,185,286),(400,257,394,265),(303,295,297,300),
    (248,321,246,324),(358,308,347,306),(299,341,297,346),
]
SIDE = [
    (218,14,204,3),(150,28,135,21),(95,72,74,70),(60,151,26,151),
    (60,210,35,207),(63,279,52,273),(107,277,105,278),
    (142,192,133,186),(195,139,174,132),(289,86,275,66),
    (339,61,332,40),(365,87,386,68),(367,133,407,109),
    (351,159,392,140),(290,186,295,165),(207,214,207,203),
    (29,339,21,325),(93,397,83,375),(148,339,132,322),
    (162,379,108,386),(206,430,177,448),(324,472,321,508),
    (404,454,406,474),(469,423,452,432),(490,393,458,403),
    (467,355,446,359),(412,332,416,337),
    (220,259,204,253),(324,215,355,195),(329,179,358,157),
    (358,228,373,217),(398,227,394,218),(426,248,433,243),
    (391,266,405,258),(346,273,347,263),(345,318,352,308),
    (394,316,393,308),(398,327,408,329),
]

CAMERAS = {
    'front': ((.041, -1.99, 1.759), (-.067, -.06, 1.685), -7, 76),
    'side': ((-1.93, -.601, 1.779), (-.069, -.001, 1.707), -7, 73),
}

# Residuals observed with the fitted mesh in the two studio cameras. These move the
# sampled skin, fleece and velvet detail into their respective UV charts.
TEXTURE_MARKS = {
    'front': [(218,1,211,3),(62,267,60,267),(22,312,10,312),(62,351,60,359),
              (332,29,333,39),(425,94,427,102),(418,136,431,147),
              (305,117,309,130),(181,180,174,184),(224,210,225,211),
              (326,193,325,196),(279,250,291,254),(251,268,251,270),
              (322,260,322,266),(181,287,185,286),(391,267,395,266),
              (292,303,298,301),(295,350,296,347),(109,427,114,429),
              (282,512,277,509),(471,356,474,353)],
    'side': [(236,6,204,3),(289,66,305,42),(157,25,140,19),(27,150,25,151),
             (152,196,138,195),(194,157,186,139),(50,272,53,273),(74,340,77,323),
             (73,389,77,374),(382,71,379,63),(403,119,402,119),
             (318,168,324,161),(204,254,204,253),(360,199,356,195),
             (413,245,431,243),(398,257,404,258),(349,272,347,264),
             (361,315,358,306),(402,325,404,327),(455,395,456,405),
             (337,493,319,506),(112,398,115,400)],
}


@lru_cache(None)
def camera_basis(view):
    location, target, roll, lens = CAMERAS[view]
    aim = (Vector(target) - Vector(location)).to_track_quat('-Z', 'Y')
    rotation = np.array((aim @ Quaternion((0, 0, 1), math.radians(roll))).to_matrix())
    return np.array(location), rotation.T * np.array([[1], [-1], [-1]]), 520 * lens / 36


def project(points, view):
    position, basis, focal = camera_basis(view)
    local = (points - position) @ basis.T
    return 260 + focal * local[..., :2] / local[..., 2:]


@lru_cache(None)
def displacement_map(view, texture=False):
    marks = np.array(TEXTURE_MARKS[view] if texture else (FRONT if view == 'front' else SIDE), dtype=float)
    xy = marks[:, :2] / 520
    def kernel(points):
        r2 = np.sum((points[:, None] - xy) ** 2, axis=-1)
        return r2 * np.log(np.maximum(1e-12, r2))
    affine = np.column_stack((np.ones(len(xy)), xy))
    matrix = np.block([[kernel(xy) + .0005 * np.eye(len(xy)), affine],
                       [affine.T, np.zeros((3, 3))]])
    weights = np.linalg.solve(matrix, np.vstack((marks[:, 2:] - marks[:, :2], np.zeros((3, 2)))))
    grid = np.stack(np.meshgrid(np.arange(131), np.arange(131)), axis=-1).reshape(-1, 2) / 130
    values = np.column_stack((kernel(grid), np.ones(len(grid)), grid)) @ weights
    return values.reshape(131, 131, 2)


def offsets(screen, view, texture=False):
    p = np.clip(screen / 4, 0, 129.999)
    ix, iy = p.astype(int).T
    u, v = (p - p.astype(int)).T[:, :, None]
    grid = displacement_map(view, texture)
    return ((1-v) * ((1-u)*grid[iy, ix] + u*grid[iy, ix+1])
            + v * ((1-u)*grid[iy+1, ix] + u*grid[iy+1, ix+1]))


@lru_cache(None)
def fit_axes():
    axes = []
    for view, (_, target, _, _) in CAMERAS.items():
        position, basis, focal = camera_basis(view)
        axes.extend(basis[:2] * focal / np.linalg.norm(target - position))
    return np.linalg.pinv(axes).T


def fit(points, texture_grid=False):
    original = np.asarray(points)
    flat = original.reshape(-1, 3)
    result = np.empty_like(flat, dtype=float)
    for i in range(0, len(flat), 32000):
        group = flat[i:i+32000]
        delta = np.column_stack([offsets(project(group, view), view) for view in CAMERAS])
        shift = delta @ fit_axes()
        # The bulb moves with the registered face as a solid volume. Interpolating the
        # spectacle and cheek landmarks across its tip would flatten its curvature.
        center = np.array([[0., -.253, 1.700]])
        nose_shift = np.column_stack([offsets(project(center, v), v) for v in CAMERAS]) @ fit_axes()
        x,y,z = group.T
        bulb = np.exp(-(x/.084)**6 - ((z-1.700)/.054)**6) * np.clip((-.180-y)/.050, 0, 1)
        fitted = group + shift*(1-bulb[:,None]) + nose_shift*bulb[:,None]
        if not texture_grid:
            residuals = np.column_stack([offsets(project(fitted,view),view,texture=True) for view in CAMERAS])
            fitted += .78 * (residuals @ fit_axes())
        result[i:i+len(group)] = fitted
    return result.reshape(original.shape)
