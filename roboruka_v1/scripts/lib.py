import math
import cadquery as cq
from params import *


# ---------- 2D → плоская деталь (экструзия по локальной Z от 0 до t) ----------
def ring_pts(c, r, n=48):
    return [(c[0] + r * math.cos(2 * math.pi * i / n), c[1] + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def hull(pts):
    P = sorted(set((round(x, 6), round(y, 6)) for x, y in pts))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in P:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(P):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def rect_pts(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def poly(pts, t, z0=0.0):
    return cq.Workplane("XY").workplane(offset=z0).polyline(pts).close().extrude(t)


def hull_plate(t, circles=(), points=()):
    """Выпуклая оболочка окружностей и точек с НАСТОЯЩИМИ дугами (удобно править в SolidWorks)."""
    N = 720
    tagged = []
    for i, (c, r) in enumerate(circles):
        for k in range(N):
            a = 2 * math.pi * k / N
            tagged.append((c[0] + r * math.cos(a), c[1] + r * math.sin(a), i))
    for p in points:
        tagged.append((p[0], p[1], -1))
    lut = {}
    for x, y, i in tagged:
        lut[(round(x, 6), round(y, 6))] = i
    H = hull([(x, y) for x, y, _ in tagged])
    tags = [lut[(round(x, 6), round(y, 6))] for x, y in H]
    n = len(H)
    # начать с вершины, где меняется источник
    start = next((k for k in range(n) if tags[k] != tags[k - 1] or tags[k] == -1), 0)
    H = H[start:] + H[:start]
    tags = tags[start:] + tags[:start]
    runs = []
    k = 0
    while k < n:
        j = k
        while j + 1 < n and tags[j + 1] == tags[k] and tags[k] != -1:
            j += 1
        runs.append((k, j))
        k = j + 1
    wp = cq.Workplane("XY").moveTo(*H[0])
    first = True
    for (a, b) in runs:
        if not first:
            wp = wp.lineTo(*H[a])
        first = False
        if b > a:
            if b - a >= 2:
                wp = wp.threePointArc(H[(a + b) // 2], H[b])
            else:
                wp = wp.lineTo(*H[b])
    if len(runs) == 1 and runs[0][1] == n - 1 and tags[0] != -1:
        c, r = circles[tags[0]]
        return circ(c, r, t)
    return wp.close().extrude(t)


def circ(c, r, t, z0=0.0):
    return cq.Workplane("XY").workplane(offset=z0).center(*c).circle(r).extrude(t)


def box2(x0, y0, x1, y1, t, z0=0.0):
    return poly(rect_pts(x0, y0, x1, y1), t, z0)


def cut_holes(s, pts, d):
    for p in pts:
        s = s.cut(circ(p, d / 2, 100, -50))
    return s


def cut_rect(s, x0, y0, x1, y1):
    return s.cut(box2(x0, y0, x1, y1, 100, -50))


def pcd(c, d, n=4, a0=45.0):
    return [(c[0] + d / 2 * math.cos(math.radians(a0 + 360 * i / n)),
             c[1] + d / 2 * math.sin(math.radians(a0 + 360 * i / n))) for i in range(n)]


def horn_star(c, radii=(7, 9, 11, 13), a0=0.0):
    """Отверстия Ø1.5 под саморезы пластиковой качалки MG90S (разметить по своей!)."""
    out = []
    for k in range(4):
        a = math.radians(a0 + 90 * k)
        out += [(c[0] + r * math.cos(a), c[1] + r * math.sin(a)) for r in radii]
    return out


def tslot(s, edge_pt, inward, t_mate):
    """Т-паз под винт M3 и гайку: edge_pt — точка на кромке, inward — единичный вектор внутрь детали."""
    ex, ey = edge_pt
    ix, iy = inward
    px, py = -iy, ix
    L = 10.0
    w = H_M3 / 2
    pts = [(ex + px * w, ey + py * w), (ex + px * w + ix * L, ey + py * w + iy * L),
           (ex - px * w + ix * L, ey - py * w + iy * L), (ex - px * w, ey - py * w)]
    s = s.cut(poly([(x, y) for x, y in pts], 100, -50))
    a, b = 4.5, 4.5 + NUT_M3_H
    nw = NUT_M3_W / 2
    pts = [(ex + px * nw + ix * a, ey + py * nw + iy * a), (ex + px * nw + ix * b, ey + py * nw + iy * b),
           (ex - px * nw + ix * b, ey - py * nw + iy * b), (ex - px * nw + ix * a, ey - py * nw + iy * a)]
    return s.cut(poly(pts, 100, -50))


# ---------- эвольвентная шестерня ----------
def _inv(a):
    return math.tan(a) - a


def gear_points(cx, cy, tooth0_deg, m=G_M, z=G_Z, pa=G_PA, bl=G_BL, n_flank=10):
    r = m * z / 2
    rb = r * math.cos(math.radians(pa))
    ra = r + m
    rf = r - 1.25 * m
    psi_p = (math.pi * m / 2 - bl) / (2 * r)
    a_p = math.radians(pa)

    def half(rho):
        rho = max(rho, rb)
        return psi_p + _inv(a_p) - _inv(math.acos(rb / rho))
    pts = []
    pitch = 2 * math.pi / z
    r_start = max(rf, rb)
    radii = [r_start + (ra - r_start) * i / n_flank for i in range(n_flank + 1)]
    for k in range(z):
        c = math.radians(tooth0_deg) + k * pitch
        h0 = half(rb)
        pts.append((rf, c - h0))
        for rho in radii:
            pts.append((rho, c - half(rho)))
        for rho in reversed(radii):
            pts.append((rho, c + half(rho)))
        pts.append((rf, c + h0))
        nxt = c + pitch - h0
        for j in range(1, 4):
            pts.append((rf, c + h0 + (nxt - (c + h0)) * j / 4))
    return [(cx + rho * math.cos(t), cy + rho * math.sin(t)) for rho, t in pts]


# ---------- размещение плоской детали в мире ----------
def cross3(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def place(wp, origin, xdir, ydir):
    """Локальная X → xdir, локальная Y → ydir, локальная Z (толщина) → xdir × ydir."""
    n = cross3(xdir, ydir)
    pl = cq.Plane(origin=cq.Vector(*origin), xDir=cq.Vector(*xdir), normal=cq.Vector(*n))
    shp = wp.val() if isinstance(wp, cq.Workplane) else wp
    return shp.moved(cq.Location(pl))


class Part:
    def __init__(self, pid, name, ru, t, solid, qty=1, note=""):
        self.pid, self.name, self.ru, self.t, self.solid, self.qty, self.note = pid, name, ru, t, solid, qty, note

    @property
    def fname(self):
        return f"{self.pid}_{self.name}"
