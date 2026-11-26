"""Sculpt the shared Santa head and expose its surfaces for the portrait groom."""
import math

import numpy as np
from mathutils import Vector
from mathutils.geometry import delaunay_2d_cdt

import santa_model as model
from santa_portrait_color import painted_material


TAU = math.tau
SKULL_CENTER = (0, .014, 1.736)
SKULL_RADII = (.182, .151, .193)
EYE_SIDES = 64
# Sine of the iris's angular radius on the eyeball. The references show an iris about
# 45% as wide as the laughing eye opening, centred in it and cut by both lids.
IRIS_RADIAL = .40
CORNEA = .0024
# One rigid spectacle frame in portrait space: rotated superellipses fitted to the gold rims
# in head.png and side.png, then a single pose solved for both views (front weighted).
FRAME_CENTER = (-.01561, -.26467, 1.74543)
FRAME_ROTATION = (-.12473, .00138, -.0515)  # about X (pitch), Y (roll), Z (yaw)
LENS_SEPARATION = .10019  # half the distance between the lens centres
LENS_SIZE = (.05388, .03733)  # half width and half height of each lens
LENS_EXPONENT = 2.45  # rounded-rectangle superellipse
LENS_WRAP = .24407  # each lens turned about its upright, outer edge back
SMILE_SIDES = 80
MOUTH_CENTER = 1.641
# The nasal bulb: a dome as deep as it is wide (after the head's widening), on a short
# wall from the face. The references show a round ball of a nose in both views.
NOSE_BASE = -.214
NOSE_DEPTH = .066
MOUTH_WIDTH = .089
POMPOM = Vector((-.376, .155, 1.660))
POMPOM_RADII = Vector((.078, .074, .077))
# Height, width, and the front and back depths of the beard silhouette.
BEARD_PROFILE = np.array([
    (1.307, .003, -.164, -.159), (1.314, .062, -.199, -.117),
    (1.331, .122, -.247, -.059), (1.355, .180, -.285, .007),
    (1.398, .225, -.308, .078), (1.448, .248, -.310, .128),
    (1.505, .255, -.280, .151), (1.554, .246, -.232, .158),
    (1.620, .225, -.203, .162), (1.672, .202, -.186, .171),
    (1.734, .180, -.155, .175), (1.810, .171, -.145, .174),
    (1.872, .144, -.127, .153),
])
# Each curl specifies its angle, start and end on the beard, width, lift, and sweep direction.
BEARD_CURLS = (
    (-2.60, .12, .82, .27, .017, -1), (-2.12, .10, .71, .24, .024, 1),
    (-1.85, .38, .90, .20, .023, -1), (-1.58, .04, .54, .22, .024, 1),
    (-1.42, .38, .86, .25, .027, 1), (-1.12, .09, .67, .20, .031, -1),
    (-.90, .40, .90, .22, .023, -1), (-.67, .11, .57, .22, .028, 1),
    (-.39, .29, .93, .24, .028, -1), (-.05, .09, .53, .21, .024, 1),
    (.12, .40, .96, .23, .034, 1), (.43, .14, .69, .20, .028, -1),
    (.65, .52, .92, .22, .023, -1), (.85, .09, .58, .23, .028, 1),
    (1.05, .39, .86, .24, .028, 1), (1.37, .09, .63, .24, .023, -1),
    (1.64, .35, .88, .25, .026, -1), (1.96, .12, .65, .24, .023, 1),
    (2.48, .30, .89, .25, .019, -1), (2.91, .08, .69, .23, .017, 1),
)


def sample_path(path, t):
    """Interpolate the position and any cross-section dimensions of a sculpted path."""
    i = min(int(t * (len(path) - 1)), len(path) - 2)
    u = t * (len(path) - 1) - i
    a, b, c, d = (path[max(0, i - 1)], path[i], path[i + 1], path[min(len(path) - 1, i + 2)])
    return b + .5 * u * (c - a + u * (2 * a - 5 * b + 4 * c - d
                                     + u * (3 * (b - c) + d - a)))


def loft(surface, steps, sides, material, *, cap=False, cap_start=True, loop=False, tiles=(1, 1), bones='head',
         portrait=None):
    rows = [[model.bm.verts.new(surface(TAU * j / sides, i / steps)) for j in range(sides)]
            for i in range(steps if loop else steps + 1)]
    if portrait:
        grid = [[tuple(v.co) for v in row + row[:1]] for row in rows]
        if loop:
            grid.append(grid[0])
        name, size, family = portrait
        material = painted_material(material, name, grid, size, family)
    for i in range(steps):
        a, b = rows[i], rows[(i + 1) % len(rows)]
        for j in range(sides):
            k = (j + 1) % sides
            vertices = (a[j], a[k], b[k], b[j])
            uv = (
                (j / sides * tiles[0], i / steps * tiles[1]),
                ((j + 1) / sides * tiles[0], i / steps * tiles[1]),
                ((j + 1) / sides * tiles[0], (i + 1) / steps * tiles[1]),
                (j / sides * tiles[0], (i + 1) / steps * tiles[1]),
            )
            model.uv_face(vertices, uv)
    if cap:
        if cap_start:
            model.bm.faces.new(tuple(reversed(rows[0])))
        model.bm.faces.new(rows[-1])
    model.finish([vertex for row in rows for vertex in row], material, bones)


def face_sculpt(x, z):
    """Continuous cheeks, bridge, nose and mouth surround on the front of the skull."""
    def volume(cx, cz, width, height):
        return math.exp(-((x - cx) / width) ** 2 - ((z - cz) / height) ** 2)

    cheek = sum(volume(sign * .112, 1.729, .070, .050) for sign in (-1, 1))
    cheek_lift = sum(volume(sign * .075, 1.763, .048, .021) for sign in (-1, 1))
    socket = sum(volume(sign * .068, 1.792, .039, .028) for sign in (-1, 1))
    wings = sum(volume(sign * .046, 1.704, .021, .015) for sign in (-1, 1))
    nostril = sum(volume(sign * .043, 1.692, .012, .0050) for sign in (-1, 1))
    bridge = volume(0, 1.761, .025, .043)
    # An ellipsoidal dome has a blunt pole in profile. Extend its lower flanks
    # to the alae with a tangent-continuous falloff.
    nose_z = (z - 1.715) / (.030 if z < 1.715 else .043)
    nose_radius = (x / .048) ** 2 + nose_z ** 2
    if nose_radius < .84:
        tip = .063 + .048 * math.sqrt(1 - nose_radius)
    else:
        flank = nose_radius - .84
        tip = .0822 * math.exp(-.730 * flank - .65 * flank * flank)
    columella = volume(0, 1.693, .023, .013)
    muzzle = volume(0, 1.657, .091, .044)
    chin = volume(0, 1.592, .083, .032)
    mouth_recess = volume(0, 1.629, .079, .024)
    x_eye = abs(x) - .068
    smile_folds, crow, forehead = model.expression_creases(x, z, math.exp)
    lower_lid = math.exp(-(x_eye / .047) ** 4
                         - ((z - 1.769 - 3.8 * x_eye ** 2 - .14 * x_eye) / .0074) ** 2)
    return (.058 * cheek + .021 * cheek_lift - .013 * socket + .040 * bridge + .56 * tip
            + .048 * wings + .008 * columella - .024 * nostril + .0042 * lower_lid
            + .059 * muzzle + .094 * chin - .038 * mouth_recess
            - .0042 * smile_folds - .0021 * crow - .00140 * forehead)


def front_y(x, z):
    _, cy, cz = SKULL_CENTER
    rx, ry, rz = SKULL_RADII
    span = math.sqrt(max(0, 1 - (x / rx) ** 2 - ((z - cz) / rz) ** 2))
    return cy - ry * span - face_sculpt(x, z) * min(1, span / .34)


def eye_outline(sign, a, outer=False):
    ex, _, ez = model.EYE_CENTER
    c, s = math.cos(a), math.sin(a)
    if outer:
        return sign * (ex + .055 * c), ez + .005 + .007 * c + (.044 if s >= 0 else .029) * s
    # A laughing squint: the upper lid arches about a quarter of the eye's width above
    # the corners and the lower lid curves gently up, so both lids cut the iris.
    if s >= 0:
        arch = .0225 * s ** 1.13 + .0008 * s * c
    else:
        arch = -.0040 * s + .0020 * s * c
    return sign * (ex + .0362 * c), ez + .0025 + .0017 * c + arch


def smile_outline(a):
    c, s = math.cos(a), math.sin(a)
    # The references laugh with a wide, fairly shallow opening under the upper teeth.
    opening = .022 * s ** .92 if s >= 0 else -.032 * (-s) ** .78
    depth = .011 * max(0, -s) ** .75
    return Vector((MOUTH_WIDTH * c, -.209 + .047 * c * c - depth,
                   MOUTH_CENTER + opening + .020 * c ** 4 + .0014 * c))


def lip_position(a, t):
    edge = smile_outline(a)
    angle_x, angle_z = math.cos(a), math.sin(a)
    lower = max(0, -angle_z)
    # A thin, rounded lower lip, as in the references.
    width = .0050 + .019 * lower ** .78
    x = edge.x + t * width * angle_x
    z = edge.z + t * width * angle_z
    skin = front_y(x, z)
    settle = t ** 3 * (4 - 3 * t)
    volume = (.0025 + .0150 * lower) * math.sin(math.pi * t) ** 1.19
    return Vector((x, (1 - settle) * edge.y + settle * skin - volume, z))


def nose_outline(a):
    c,s = math.cos(a),math.sin(a)
    return .066*c*(1-.46*max(0,s)), 1.714+(.047 if s>0 else .027)*s


def join_skin_rings(rows, material, surface_uv=False):
    """Connect sculpted rings to their last, shared row of skull vertices."""
    sides = len(rows[0])
    for step, (a, b) in enumerate(zip(rows, rows[1:])):
        for i in range(sides):
            j = (i + 1) % sides
            vertices = (a[i], a[j], b[j], b[i])
            uv = [(i / sides, step / (len(rows) - 1)), ((i + 1) / sides, step / (len(rows) - 1)),
                  ((i + 1) / sides, (step + 1) / (len(rows) - 1)), (i / sides, (step + 1) / (len(rows) - 1))]
            model.uv_face(vertices, [model.face_uv(v.co) for v in vertices] if surface_uv else uv)
    model.finish([v for row in rows[:-1] for v in row], material, 'head')


def build_skull():
    """Create one skin surface with boundaries for both eyelids and the lips."""
    _, cy, cz = SKULL_CENTER
    rx, ry, rz = SKULL_RADII
    count = 128
    boundary = [
        [(rx * math.cos(TAU * i / count), cz + rz * math.sin(TAU * i / count)) for i in range(count)],
        *[[eye_outline(sign, TAU * i / EYE_SIDES, outer=True) for i in range(EYE_SIDES)] for sign in (-1, 1)],
        [(p.x, p.z) for p in [lip_position(TAU * i / SMILE_SIDES, 1) for i in range(SMILE_SIDES)]],
        [nose_outline(TAU*i/72) for i in range(72)],
    ]
    bounds = [(min(x for x, _ in ring), max(x for x, _ in ring),
               min(z for _, z in ring), max(z for _, z in ring)) for ring in boundary[1:]]

    def inside_opening(x, z):
        for ring, (x0, x1, z0, z1) in zip(boundary[1:], bounds):
            if not (x0 <= x <= x1 and z0 <= z <= z1):
                continue
            inside = False
            for (ax, az), (bx, bz) in zip(ring, ring[1:] + ring[:1]):
                if (az > z) != (bz > z) and x < ax + (bx - ax) * (z - az) / (bz - az):
                    inside = not inside
            if inside:
                return True
        return False

    coordinates, edges, original_rings = [], [], []
    for ring in boundary:
        ids = list(range(len(coordinates), len(coordinates) + len(ring)))
        coordinates.extend(Vector(p) for p in ring)
        edges.extend(zip(ids, ids[1:] + ids[:1]))
        original_rings.append(ids)

    # Use a denser grid through the nose and expression creases.
    for iz in range(-47, 48):
        z = cz + iz * .004
        for ix in range(-44, 45):
            x = (ix + (iz % 2) * .5) * .004
            if (x / rx) ** 2 + ((z - cz) / rz) ** 2 >= .998 or inside_opening(x, z):
                continue
            coordinates.append(Vector((x, z)))
            nose = abs(x) < .073 and 1.687 < z < 1.775
            eyelid = .017 < abs(x) < .153 and 1.733 < z < 1.806
            forehead = abs(x) < .082 and 1.812 < z < 1.878
            if (nose or eyelid or forehead) and not inside_opening(x + .0017, z + .0018):
                coordinates.append(Vector((x + .0017, z + .0018)))

    points, _, triangles, originals, _, _ = delaunay_2d_cdt(coordinates, edges, [], 0, 1e-6)
    original_to_point = {i: j for j, indices in enumerate(originals) for i in indices}
    rings = [[original_to_point[i] for i in ring] for ring in original_rings]
    perimeter = set(rings[0])
    vertices = [
        model.bm.verts.new((x, cy if i in perimeter else front_y(x, z), z))
        for i, (x, z) in enumerate(points)
    ]
    for triangle in triangles:
        cx = sum(points[i].x for i in triangle) / 3
        height = sum(points[i].y for i in triangle) / 3
        if not inside_opening(cx, height):
            face = tuple(vertices[i] for i in triangle)
            model.uv_face(face, [model.face_uv(v.co) for v in face])

    row = [vertices[i] for i in rings[0]]
    for step in range(1, 26):
        phi = (math.pi / 2) * step / 26
        radius = math.cos(phi)
        back = [model.bm.verts.new((radius * x, cy + ry * math.sin(phi), cz + radius * (z - cz)))
                for x, z in boundary[0]]
        for i in range(count):
            j = (i + 1) % count
            face = (row[i], row[j], back[j], back[i])
            model.uv_face(face, [model.face_uv(v.co) for v in face])
        vertices.extend(back)
        row = back
    pole = model.bm.verts.new((0, cy + ry, cz))
    for i in range(count):
        face = (row[i], row[(i + 1) % count], pole)
        model.uv_face(face, [model.face_uv(v.co) for v in face])
    model.finish(vertices + [pole], model.FACE, 'head')
    return [[vertices[i] for i in ring] for ring in rings[1:]]


def build_eye(sign, attachment):
    ex, ey, ez = model.EYE_CENTER
    ball_z = ez + model.EYEBALL_LIFT
    bone = 'eye.L' if sign > 0 else 'eye.R'

    def eye_y(x, z):
        span = max(0, 1 - ((x - sign * ex) / .044) ** 2 - ((z - ball_z) / .041) ** 2)
        return ey - .043 * math.sqrt(span)

    def white(a, t):
        x, z = eye_outline(sign, a)
        t *= .999
        x = (1 - t) * x + t * sign * ex
        z = (1 - t) * z + t * (ball_z + .0035)
        return x, eye_y(x, z), z

    loft(white, 8, EYE_SIDES, model.WHITE, cap=True)
    rows = []
    for t in (0, .045, .095, .16, .24, .34, .47, .62, .76, .87, .95):
        row = []
        for i in range(EYE_SIDES):
            a = TAU * i / EYE_SIDES
            x, z = eye_outline(sign, a)
            ox, oz = eye_outline(sign, a, outer=True)
            s = math.sin(a)
            xx, zz = x + (ox - x) * t, z + (oz - z) * t
            edge = min(eye_y(x, z) - .0011, front_y(x, z) - .0003)
            blend = 1 - t * t * (3 - 2 * t)
            swell = (.0052 if s >= 0 else .0070) * math.sin(math.pi * t) ** 2 * abs(s)
            lid_roll = .0029 * math.exp(-((t - .130) / .123) ** 2) * abs(s)
            upper_fold = .0033 * math.exp(-((t - .53) / .157) ** 2) * max(0, s)
            yy = (front_y(xx, zz) + (edge - front_y(x, z)) * blend - swell
                  - lid_roll + upper_fold + .0002 * (1 - blend))
            # Keep the lid ahead of the curved iris while it rotates on the eye bone.
            settle = max(0, (t - .72) / .28)
            yy = min(yy, eye_y(xx, zz) - .0028 + .027 * settle ** 2)
            row.append(model.bm.verts.new((xx, yy, zz)))
        rows.append(row)
    join_skin_rings(rows + [attachment], model.FACE, surface_uv=True)
    lashline, widths = [], []
    for i in range(35):
        a = math.pi*i/34
        x, z = eye_outline(sign, a)
        y = min(eye_y(x,z)-.0011, front_y(x,z)-.0003)
        lashline.append((x, y-.0006, z+.0003))
        widths.append(.0002 + .0012*math.sin(a)**.7)
    model.tube(lashline, widths, model.NOSTRIL, sides=6, sub=1)
    # The portrait fit tilts the face down about 11 degrees around the eyes, so this rest
    # gaze ends up level, toward the viewer, as in the references.
    forward = Vector((-.07, -1, .19)).normalized()
    across = forward.cross(Vector((0, 0, 1))).normalized()
    up = across.cross(forward)
    center = Vector((sign * ex, ey, ball_z))

    def iris(a, t):
        fraction = 1 - .999 * t
        radial = IRIS_RADIAL * fraction
        direction = forward * math.sqrt(1 - radial ** 2) + radial * (
            math.cos(a) * across + math.sin(a) * up)
        # A shallow corneal dome, steeper than the eyeball, keeps the key light's
        # catchlight inside the iris; it stays behind the lids as the eye turns.
        return center + direction * Vector((.044, .0437, .041)) + forward * CORNEA * (1 - fraction ** 2)

    loft(iris, 13, 64, model.IRIS, bones=bone)


def build_glasses():
    """Model rigid gold spectacles directly in the fitted portrait space.

    The pose and lens size come from rotated superellipses fitted to the rims in both
    reference photographs (front weighted, since the profile places the face lower).
    Being one rigid, symmetric frame, the rims stay flat rounded rectangles from any
    angle; the frame is moved toward the viewer only as far as the fitted skin requires.
    The vertices are registered in model.UNFITTED so the portrait warp leaves them alone.
    """
    from mathutils import Euler
    from mathutils.bvhtree import BVHTree
    from santa_portrait_fit import fit

    first = len(model.bm.verts)
    faces = [f for f in model.bm.faces if model.MATS[f.material_index].name == model.FACE]
    vertices = list({v for f in faces for v in f.verts})
    ids = {v: i for i, v in enumerate(vertices)}
    points = np.array([tuple(v.co) for v in vertices]) * np.array(model.HEAD_SCALE)
    points[:, 2] = model.head_height(points[:, 2])
    skin = BVHTree.FromPolygons(fit(points), [[ids[v] for v in f.verts] for f in faces])

    turn = Euler(FRAME_ROTATION, 'XYZ').to_matrix()
    back = turn @ Vector((0, 1, 0))
    separation = LENS_SEPARATION
    width, height = LENS_SIZE

    def lens(side, a):
        c, s = math.cos(a), math.sin(a)
        u = math.copysign(abs(c) ** (2 / LENS_EXPONENT), c) * width
        v = math.copysign(abs(s) ** (2 / LENS_EXPONENT), s) * height
        # Each lens turns about its own upright so its outer edge sweeps back around the face.
        wrap = side * LENS_WRAP
        return Vector((side * separation + u * math.cos(wrap), u * math.sin(wrap), v))

    origin = Vector(FRAME_CENTER)

    def place(local):
        return origin + turn @ local

    def depth_in_skin(point, clearance):
        """How far `point` must move toward the viewer to keep `clearance` from the skin."""
        hit = skin.ray_cast(point, -back, .06)
        if hit[0] is not None:
            return hit[3] + clearance
        hit = skin.ray_cast(point, back, clearance)
        return clearance - hit[3] if hit[0] is not None else 0

    rims = [lens(side, TAU * i / 96) for side in (-1, 1) for i in range(96)]
    push = max(depth_in_skin(place(p), .0028) for p in rims)
    print(f'[glasses] frame moved {1000 * push:.1f} mm toward the viewer to clear the skin', flush=True)
    origin -= back * push
    for side in (-1, 1):
        rim = [place(lens(side, TAU * i / 96)) for i in range(96)]
        model.tube(rim + rim[:1], [.0021] * 97, model.WIRE, sides=8, sub=1, cap=False)

    # A bridge arching a little above the inner top corners, set back toward the nose.
    corner = .70
    ends = lens(-1, corner), lens(1, math.pi - corner)
    top = max(e.z for e in ends) + .0085
    bridge = [ends[0], Vector((-.024, .004, top - .0025)), Vector((0, .006, top)),
              Vector((.024, .004, top - .0025)), ends[1]]
    bridge = [place(p) for p in bridge]
    bridge = [p - back * depth_in_skin(p, .003) for p in bridge]
    model.tube([Vector(sample_path(np.array(bridge), i / 24)) for i in range(25)], [.0019] * 25,
               model.WIRE, sides=8, sub=1)

    for side in (-1, 1):
        # Nose pads rest on the nose behind the inner edge of each lens.
        pad = place(Vector((side * (separation - .83 * width), 0, .23 * height)))
        hit = skin.ray_cast(pad, back, .08)
        pad = hit[0] - back * .0035 if hit[0] is not None else pad + back * .018
        anchor = place(lens(side, .32 if side < 0 else math.pi - .32))
        model.tube([anchor, anchor.lerp(pad, .5) + back * .002, pad], [.0012] * 3, model.WIRE, sides=6)
        model.ellipsoid(pad, (.0030, .0018, .0048), model.WIRE, seg=12, rings=8)
        # Hinges at the outer corners, and temples running back along the head to the ears.
        hinge = place(lens(side, math.pi - .38 if side < 0 else .38) + Vector((side * .0035, .002, 0)))
        model.ellipsoid(hinge, (.0050, .0036, .0042), model.WIRE, seg=14, rings=8)
        temple = [hinge]
        for k, y in enumerate((-.19, -.12, -.05, .02)):
            z = hinge.z - .003 * k
            hit = skin.ray_cast(Vector((side * .40, y, z)), Vector((-side, 0, 0)), .40)
            x = hit[0].x + side * .007 if hit[0] is not None else side * .225
            temple.append(Vector((x, y, z)))
        temple.append(Vector((temple[-1].x, .07, temple[-1].z - .035)))
        model.tube(temple, [.0024] + [.0019] * (len(temple) - 2) + [.0014], model.WIRE, sides=8)
    model.bm.verts.ensure_lookup_table()
    model.UNFITTED.update(model.bm.verts[i] for i in range(first, len(model.bm.verts)))


def build_smile(attachment):
    rows = [[model.bm.verts.new(lip_position(TAU * i / SMILE_SIDES, j / 10))
             for i in range(SMILE_SIDES)] for j in range(10)]
    join_skin_rings(rows + [attachment], model.LIP)
    grid = [[tuple(v.co) for v in row+row[:1]] for row in rows+[attachment]]
    painted_material(model.LIP,model.LIP,grid,(512,128),'lip')
    middle = Vector((0, -.160, MOUTH_CENTER - .008))

    def cavity(a, t):
        t *= .999
        return smile_outline(a).lerp(middle, t) + Vector((0, .001 + .014 * math.sin(math.pi * t), 0))

    loft(cavity, 9, 72, model.LAUGH, portrait=(model.LAUGH,(512,256),'cavity'))
    tooth_profile = (
        (-.066, .0080, .0075), (-.052, .0090, .0081), (-.035, .0103, .0081), (-.013, .0140, .0090),
        (.0135, .0137, .0089), (.036, .0102, .0081), (.052, .0088, .0082), (.067, .0081, .0072),
    )
    for x, width, height in tooth_profile:
        spread = x / MOUTH_WIDTH
        z = 1.649 + .006 * abs(spread) ** 1.6 + .0009 * spread
        origin = Vector((x, -.217 + .032 * spread ** 2, z))
        radii = Vector((width * 1.025, .007, height))

        def rounded_tooth(co):
            offset = co - origin
            return origin + Vector([math.copysign(r * abs(v / r) ** .68, v)
                                    for v, r in zip(offset, radii)])

        model.ellipsoid(origin, radii, model.TEETH, seg=20, rings=12, warp=rounded_tooth)
    def tongue_shape(co):
        co.z -= .0018 * math.exp(-(co.x / .009) ** 2 - ((co.y + .172) / .017) ** 2)
        co.z += .41 * (co.y + .184)
        return co

    # The tongue's top fills the lower part of the opening; its tip stays behind the lower lip.
    def tongue(a,t):
        phi = math.pi*(.0005+.999*t)
        return tongue_shape(Vector((.002+.062*math.cos(a)*math.sin(phi),
                                    -.188+.040*math.sin(a)*math.sin(phi),1.605+.018*math.cos(phi))))
    loft(tongue,24,48,model.TONGUE,cap=True,portrait=(model.TONGUE,(512,256),'tongue'))


def build_ear(sign):
    """Form the ear with a rolled rim and recessed concha visible in profile."""
    def shell(a, t):
        c, s = math.cos(a), math.sin(a)
        radius = 1 - .999 * t
        y = .014 + radius * (.031 * c + .010 * s)
        z = 1.738 + radius * .045 * s
        rim = .025 * math.exp(-((t - .18) / .15) ** 2)
        ridge = .012 * math.exp(-((t - .59) / .13) ** 2) * (.52 + .48 * math.sin(a + .34))
        lobe = .007 * max(0, -s) ** 2 * math.sin(math.pi * t)
        bowl = .024 * (1 - math.exp(-(t / .23) ** 2))
        return sign * (.169 + bowl + rim + ridge + lobe), y, z

    loft(shell, 16, 48, model.SKIN, cap=True,
         portrait=('Ear '+('left' if sign>0 else 'right'),(384,256),'ear'))


def build_nose(attachment):
    """Join the bridge and nostril wings to a single rounded, undercut nasal tip."""
    rows = [attachment]
    for i in range(1,31):
        t = i/30
        row = []
        for j, vertex in enumerate(attachment):
            a = TAU*j/len(attachment)
            c,s = math.cos(a),math.sin(a)
            wing = math.exp(-((abs(c)-.90)/.20)**2-((s+.38)/.31)**2)
            x, z = .050*c+.006*wing*c, 1.716+.034*s-.002*wing
            if t < .38:
                u = t/.38
                ease = u*u*(3-2*u)
                co = vertex.co.lerp(Vector((x, NOSE_BASE-.006*wing, z)), ease)
                co.y -= .003*math.sin(math.pi*u)
            else:
                phi = min((t-.38)/.62,.9999)*math.pi/2
                radial = math.cos(phi)
                xx,zz = radial*x, 1.716+radial*(z-1.716)
                pocket = math.exp(-((abs(xx)-.034)/.011)**2-((zz-1.695)/.0055)**2)
                co = Vector((xx,NOSE_BASE-NOSE_DEPTH*math.sin(phi)-.006*wing*radial+.009*pocket,zz))
            row.append(model.bm.verts.new(co))
        rows.append(row)
    model.uv_face(rows[-1],[model.face_uv(v.co) for v in rows[-1]])
    join_skin_rings(list(reversed(rows)), model.FACE, surface_uv=True)


def beard_root_height(front):
    return 1.720 - .153 * front ** 4.1 + .020 * front ** 7


def beard_curl_relief(a, t):
    """Blend swept, tapered curls into the volume without introducing intersecting locks."""
    relief = 0
    for center, start, end, width, rise, direction in BEARD_CURLS:
        if start < t < end:
            u = (t - start) / (end - start)
            offset = direction * (.185 * math.sin(TAU * u - .45) + .065 * u)
            delta = (a - center - offset + math.pi) % TAU - math.pi
            relief += rise * math.exp(-(delta / width) ** 2) * math.sin(math.pi * u) ** 1.6
    return relief


def beard_surface(a, t):
    facing = math.cos(a)
    front, back = max(0, facing), max(0, -facing)
    wave = 17 * a + .65 * math.sin(5 * a + .43) + .51 * math.sin(7 * a)
    root = beard_root_height(front) + .147 * back ** 1.15 + .0033 * math.cos(wave)
    z = (1 - t) * root + t * BEARD_PROFILE[0, 0]
    w, near, far = (float(np.interp(z, BEARD_PROFILE[:, 0], BEARD_PROFILE[:, i]))
                     for i in (1, 2, 3))
    body = math.sin(math.pi * t) ** .67
    phase = 2 * a + .36 * math.sin(3 * a + .3)
    sweep = (.165 + .034 * math.sin(2 * a)) * math.sin(1.17 * TAU * t + phase)
    curl = .075 * math.sin(2.27 * TAU * t - a + .36 * math.sin(5 * a))
    curl *= math.exp(-((t - .67) / .25) ** 2)
    swing = sweep + curl
    angle = a + body * swing
    # Sculpt the swept locks into the surface so their edges meet in rounded valleys.
    ridge = (.5 + .5 * math.cos(wave + .37 * math.sin(8 * t + a))) ** 1.33
    swell = .82 + .17 * math.cos(10 * t + 3 * a) + .13 * math.sin(15 * t - 2 * a)
    ripple = .0034 * math.cos(2 * wave + 3 * t) + .0013 * math.cos(3 * wave - 5 * t)
    locks = beard_curl_relief(a, t)
    relief = (.025 * swell * (ridge - .43) + ripple) * body + locks
    center = (near + far) / 2
    depth = (far - near) / 2
    # The exposed root ring slips behind the lower lip and then grows forward.
    keep_mouth_clear = .040 * front ** 6 * math.exp(-(t / .096) ** 2)
    clear_shoulders = .020 * math.exp(-((z - 1.405) / .064) ** 2) * math.sin(angle) ** 4
    nape = .090*back**.72 * math.exp(-((z-1.610)/.16)**2)
    scallops = .008 * math.cos(wave + .7) * body * math.sin(t * math.pi / 2)
    right_taper = max(0, math.sin(angle)) ** 2
    shift = -(.016 + .012 * right_taper) * math.exp(-((z - 1.470) / .138) ** 2)
    return Vector((shift + (w + relief) * math.sin(angle),
                   center - (depth + relief) * math.cos(angle) + keep_mouth_clear - clear_shoulders + nape,
                   z + scallops + .14 * locks))


def lock_surface(path, a, t):
    x, y, z, w, depth = map(float, sample_path(path, t))
    start = Vector(sample_path(path, max(0, t - .002))[:3])
    end = Vector(sample_path(path, min(1, t + .002))[:3])
    tangent = (end - start).normalized()
    side = min(1, max(0, (y + .15) / .09))
    across = tangent.cross(Vector((x * (2 + 9 * side), -1, .06))).normalized()
    front = across.cross(tangent)
    ripple = 1 + .075 * math.cos(6 * a + 4 * t)
    return Vector((x, y, z)) + w * math.cos(a) * across + depth * math.sin(a) * ripple * front


def hair_paths():
    moustache = np.array([
        (-.008, -.215, 1.678, .010, .010), (.012, -.226, 1.676, .015, .015),
        (.037, -.230, 1.678, .019, .020), (.060, -.227, 1.670, .019, .018),
        (.093, -.214, 1.659, .021, .017), (.121, -.189, 1.650, .022, .015),
        (.150, -.174, 1.655, .019, .013), (.164, -.169, 1.670, .015, .011),
        (.159, -.170, 1.685, .010, .008), (.146, -.173, 1.690, .005, .004),
        (.136, -.174, 1.685, .0009, .0007),
    ])
    brow_profile = [
        (.020, 1.835, .0023, .0023), (.031, 1.846, .012, .0090),
        (.049, 1.856, .017, .0120), (.069, 1.853, .018, .0128),
        (.091, 1.841, .014, .0105),
        (.111, 1.824, .010, .0072), (.130, 1.807, .0018, .0024),
    ]
    from santa_portrait_fit import from_portraits
    brow_front = [(245,173),(238,169),(224,166),(210,169),(192,178),(181,189),(170,202)]
    brow_side = [(375,162),(370,156),(360,150),(346,154),(330,163),(319,174),(308,187)]
    brow = []
    for front, side, (_,_,width,depth) in zip(brow_front,brow_side,brow_profile):
        p = from_portraits(front,side)
        x = abs(p[0]/model.HEAD_SCALE.x)
        z = np.interp(p[2],model.HEAD_HEIGHTS[:,1],model.HEAD_HEIGHTS[:,0])
        y = min(p[1]/model.HEAD_SCALE.y,front_y(x,z)-.003)
        brow.append((x,y,z,width,depth))
    sideburn = [
        (.133, -.026, 1.897, .025, .019), (.148, -.055, 1.853, .030, .022),
        (.177, -.089, 1.819, .024, .019), (.180, -.094, 1.781, .021, .016),
        (.178, -.060, 1.748, .022, .020), (.188, -.071, 1.718, .026, .021),
        (.194, -.104, 1.688, .024, .020), (.175, -.137, 1.659, .011, .008),
        (.148, -.151, 1.643, .003, .003),
    ]
    temple_sweep = [
        (.138, -.073, 1.871, .012, .009), (.156, -.101, 1.840, .020, .011),
        (.179, -.106, 1.811, .020, .014), (.189, -.076, 1.788, .019, .014),
        (.183, -.039, 1.785, .019, .014), (.173, -.004, 1.789, .017, .013),
        (.173, .034, 1.778, .017, .014), (.172, .066, 1.752, .014, .011),
        (.152, .086, 1.733, .005, .005),
    ]
    nape = [
        (.153, .023, 1.847, .018, .015), (.171, .049, 1.807, .027, .019),
        (.174, .076, 1.776, .026, .021), (.169, .071, 1.742, .028, .023),
        (.180, .070, 1.710, .029, .024), (.186, .105, 1.677, .028, .020),
        (.176, .122, 1.643, .015, .012),
    ]
    for sign in (-1, 1):
        mirror = np.array((sign, 1, 1, 1, 1))
        yield 'Moustache', moustache * mirror
        yield 'Eyebrow', np.array(brow) * mirror
        for name, profile in (('Temple hair',sideburn),('Temple curl',temple_sweep)):
            temple = np.array(profile)*mirror
            temple[:,1] += (.065 if sign>0 else .046)*np.exp(-((temple[:,2]-1.813)/.078)**2)
            yield name,temple
        yield 'Temple hair', np.array(nape) * mirror


def brim_surface(a, t):
    b = TAU * t
    c, s = math.cos(a), math.sin(a)
    swell = 1 + .068 * math.cos(7 * a + .6 * math.sin(b)) + .032 * math.sin(13 * a - 3 * b)
    x = (.188 + .049 * swell * math.cos(b)) * c
    y = .010 + (.165 + .046 * swell * math.cos(b)) * s
    front = max(0, -s)
    back = max(0, s)
    right = max(0, c)
    fall = max(0, -c) * front
    arch = .071 * front ** 2 - .085 * back ** 1.35 - .010 * c * c - .012 * fall - .013 * right * front
    x -= .025 * fall + .009 * right ** 2
    y -= .011 * fall
    thickness = .052 + (.026 if math.sin(b) > 0 else .013) * front ** 1.6
    thickness += .010 * fall - .013 * right * front
    z = 1.904 + .147 * x + arch + thickness * swell * math.sin(b)
    z -= .017*max(0,-math.sin(b))**1.4*(.55+max(0,-c))
    return Vector((x, y, z))


def pompom_surface(a, t):
    b = math.pi * t
    direction = Vector((math.sin(b) * math.cos(a), math.sin(b) * math.sin(a), math.cos(b)))
    wobble = 1 + .029 * math.sin(7 * a + 4 * b) * math.sin(b) + .032 * math.sin(11 * b - 3 * a) * math.sin(b)
    return POMPOM + direction * POMPOM_RADII * wobble


def build_cap():
    path = np.array([
        (0, .025, 1.945, .121), (-.012, .019, 1.973, .146), (-.058, .021, 2.009, .128),
        (-.137, .043, 2.037, .112), (-.220, .071, 2.010, .100),
        (-.281, .101, 1.952, .084), (-.320, .127, 1.867, .069),
        (-.349, .145, 1.781, .052), (-.376, .155, 1.695, .026),
    ])
    def cap_surface(a, t):
        x, y, z, radius = map(float, sample_path(path, t))
        before = Vector(sample_path(path, max(0, t - .002))[:3])
        after = Vector(sample_path(path, min(1, t + .002))[:3])
        tangent = (after - before).normalized()
        across = tangent.cross(Vector((0, -1, 0))).normalized()
        front = across.cross(tangent)
        along_fold = math.exp(-((t - .49) / .305) ** 2)
        valley_angle = .92 + .96 * t
        valley = math.exp(-12 * (1 - math.cos(a - valley_angle)))
        ridge = math.exp(-22 * (1 - math.cos(a - valley_angle + .53)))
        return_fold = math.exp(-21 * (1 - math.cos(a - valley_angle - .46)))
        radius *= 1 + along_fold * (.30 * ridge - .74 * valley + .13 * return_fold)
        radius += .004 * math.exp(-((t - .68) / .25) ** 2) * math.sin(8 * a + TAU * 1.6 * t)
        z -= .085 * max(0, -math.sin(a)) ** 1.35 * math.exp(-(t / .24) ** 2)
        crown = math.exp(-((t-.34)/.21)**2) * max(0, math.sin(a))
        return Vector((x, y-.041*crown, z+.007*crown)) + radius * (math.cos(a) * across + .94 * math.sin(a) * front)

    loft(cap_surface, 48, 56, model.HAT, cap=True, cap_start=False,
         portrait=('Folded velvet', (1024,1024), 'velvet'))
    loft(brim_surface, 24, 96, model.FUR, loop=True,
         portrait=('Fur brim', (1536,512), 'hair'))

    loft(lambda a, t: pompom_surface(a, .0005 + .999*t), 30, 48, model.FUR, cap=True,
         portrait=('Pompom fibers', (768,512), 'hair'))


def build_head():
    def skin_depth(x,z):
        radius = (x/.051)**2 + ((z-1.715)/.036)**2
        return min(front_y(x,z), NOSE_BASE-NOSE_DEPTH*math.sqrt(1-radius)) if radius<1 else front_y(x,z)

    grid = [[(x, skin_depth(x,z), z) for x in np.linspace(-.2,.2,105)]
            for z in np.linspace(1.512,1.942,113)]
    painted_material(model.FACE, model.FACE, grid, (768,768), 'skin')
    right_eye, left_eye, lips, nose = build_skull()
    build_nose(nose)
    for sign, socket in ((-1, right_eye), (1, left_eye)):
        build_ear(sign)
        build_eye(sign, socket)
    build_glasses()
    build_smile(lips)
    loft(beard_surface, 62, 112, model.HAIR, cap=True, cap_start=False,
         portrait=('Combed beard', (2048,1024), 'beard'))
    for name, path in hair_paths():
        steps, sides = {'Moustache': (44, 20), 'Eyebrow': (30, 15), 'Temple hair': (40, 18),
                        'Temple curl': (32, 14)}[name]
        side = 'left' if path[len(path)//2, 0] > 0 else 'right'
        if name == 'Temple hair' and path[len(path)//2, 1] > 0:
            name = 'Nape'
        loft(lambda a, t: lock_surface(path, a, t), steps, sides, model.HAIR, cap=True,
             portrait=(name+' '+side, (384,768), 'hair'))
    build_cap()
