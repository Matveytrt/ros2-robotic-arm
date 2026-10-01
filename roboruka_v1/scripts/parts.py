"""Все детали из оргстекла как плоские заготовки: локальная XY = контур, Z = толщина (0…t)."""
import math, os, csv
import numpy as np
from lib import *

# ================= Y-раскладка (мир, левый борт +Y). Ось клешни лежит в плоскости Y=0 =================
Y_FAL = (FA_INNER / 2 - 3.5, FA_INNER / 2 - 0.5)          # 9…12   предплечье левое (серва наклона)
Y_FAR = (Y_FAL[0] - FA_INNER - T3, Y_FAL[0] - FA_INNER)  # -19…-16 предплечье правое (на качалке локтя)
Y_PS_TAB = Y_FAL[0]                                      # 9: ушки сервы наклона на внутренней грани
Y_WA = (Y_PS_TAB + S_HORN_FACE, Y_PS_TAB + S_HORN_FACE + T3)   # 20…23 кисть A (на качалке наклона)
Y_WB = (Y_FAR[0] - 1.0 - T3, Y_FAR[0] - 1.0)             # -23…-20 кисть B (на оси)
Y_EL_TAB = Y_FAR[0] - SV_HORN_FACE                       # -34: ушки MG996R локтя (снаружи правого плеча)
Y_UAR = (Y_EL_TAB, Y_EL_TAB + T5)                        # -34…-29 плечо правое (серва локтя)
Y_UAL = (Y_FAL[1] + GAP, Y_FAL[1] + GAP + T5)            # 12.5…17.5 плечо левое (на качалке плеча)
Y_TWL = (Y_UAL[1] + SV_HORN_FACE - T5, Y_UAL[1] + SV_HORN_FACE)   # 27.5…32.5 стойка левая (MG996R плеча)
Y_TWR = (Y_UAR[0] - 1.0 - T5, Y_UAR[0] - 1.0)            # -40…-35 стойка правая (ось M4)
UA_SPACER_L = Y_UAL[0] - Y_UAR[1]                         # 41.5


def rounded_square(a, r, t):
    h = a / 2 - r
    return hull_plate(t, circles=[((sx * h, sy * h), r) for sx in (-1, 1) for sy in (-1, 1)])


# ================= СТИЛЬ: облегчающие окна =================
def _face_of(solid):
    return max(solid.faces("<Z").vals(), key=lambda f: f.Area())


def windows(solid, frame, keeps_c=(), keeps_poly=(), ribs=(), min_area=30.0, rnd=2.5):
    """Вырезает окна: внутренний контур (отступ frame от края) минус «островки» вокруг отверстий и минус рёбра."""
    try:
        w = _face_of(solid).outerWire().offset2D(-frame, "arc")[0]
    except Exception:
        return solid
    reg = cq.Workplane("XY").add(cq.Face.makeFromWires(w)).wires().toPending().extrude(1).translate((0, 0, -0.5))
    for (c, r) in keeps_c:
        reg = reg.cut(circ(c, r, 3, -1.5))
    for pts in keeps_poly:
        reg = reg.cut(poly(pts, 3, -1.5))
    for (p0, p1, wdt) in ribs:
        reg = reg.cut(hull_plate(3, circles=[(p0, wdt / 2), (p1, wdt / 2)]).translate((0, 0, -1.5)))
    out = solid
    for f in reg.faces("<Z").vals():
        if f.Area() < min_area:
            continue
        try:
            ow = f.outerWire().offset2D(-rnd, "arc")[0].offset2D(rnd, "arc")[0]
            inner = []
            for iw in f.innerWires():
                try:
                    inner.append(iw.offset2D(rnd * 0.6, "arc")[0])
                except Exception:
                    inner.append(iw)
            ff = cq.Face.makeFromWires(ow, inner)
            if ff.Area() < min_area:
                continue
            cutter = cq.Workplane("XY").add(ff).wires().toPending().extrude(200).translate((0, 0, -100))
            out = out.cut(cutter)
        except Exception:
            continue
    return out


def waist(solid, x0, x1, h_mid, R=140.0):
    """Стиль A: вогнутые бока в середине звена (как у синей руки)."""
    xm = (x0 + x1) / 2
    for sgn in (-1, 1):
        solid = solid.cut(circ((xm, sgn * (R + h_mid)), R, 200, -100))
    return solid


def grow_rect(x0, y0, x1, y1, g):
    return rect_pts(x0 - g, y0 - g, x1 + g, y1 + g)


def truss_ribs(x0, x1, h, pitch=24.0, w=5.0, yc=0.0):
    ribs = []
    n = max(1, int((x1 - x0) / pitch))
    xs = [x0 + (x1 - x0) * i / n for i in range(n + 1)]
    for i in range(n):
        ya, yb = (yc - h, yc + h) if i % 2 == 0 else (yc + h, yc - h)
        ribs.append(((xs[i], ya), (xs[i + 1], yb), w))
    return ribs


def styled(solid, feats_c, feats_poly, x0, x1, h, frame, waist_h=None, slot=None):
    """Общая обработка звена по STYLE. feats_c: [(центр, R островка)], feats_poly: [полигоны островков]."""
    if STYLE == "A":
        if waist_h:
            solid = waist(solid, x0, x1, waist_h)
        if slot:
            solid = solid.cut(hull_plate(200, circles=[(slot[0], slot[2] / 2), (slot[1], slot[2] / 2)]).translate((0, 0, -100)))
        return solid
    spine = [((x0 - 30, 0), (x1 + 40, 0), 5.0)]           # продольное ребро держит «островки» вокруг отверстий
    if STYLE == "B":
        return windows(solid, frame, feats_c, feats_poly, truss_ribs(x0, x1, h) + spine)
    return windows(solid, frame, feats_c, feats_poly, spine)


# ================= ОСНОВАНИЕ =================
def p01_bottom():
    s = rounded_square(BASE_BOT, BASE_R, T5)
    s = cut_holes(s, [(sx * STANDOFF_POS, sy * STANDOFF_POS) for sx in (-1, 1) for sy in (-1, 1)], H_M3)
    s = cut_holes(s, [(sx * TABLE_HOLE_POS, sy * TABLE_HOLE_POS) for sx in (-1, 1) for sy in (-1, 1)], H_M4)
    s = cut_rect(s, -55, -8, -45, 8)          # окно под провод шагового
    return s


def p02_top():
    s = rounded_square(BASE_TOP, BASE_R, T5)
    s = cut_holes(s, [(sx * STANDOFF_POS, sy * STANDOFF_POS) for sx in (-1, 1) for sy in (-1, 1)], H_M3)
    s = cut_holes(s, [(0, 0)], NEMA_BOSS_D + 0.5)
    h = NEMA_HOLE_SP / 2
    s = cut_holes(s, [(sx * h, sy * h) for sx in (-1, 1) for sy in (-1, 1)], H_M3)
    s = cut_holes(s, pcd((0, 0), 2 * RING_LOW_SCREW_R, 4, 0), H_M3)
    return s


def p03_ring_low():
    s = circ((0, 0), RING_LOW_OD / 2, T5)
    s = cut_holes(s, [(0, 0)], RING_ID)
    return cut_holes(s, pcd((0, 0), 2 * RING_LOW_SCREW_R, 4, 0), H_M3)


def p05_ring_up():
    s = circ((0, 0), RING_UP_OD / 2, T5)
    s = cut_holes(s, [(0, 0)], RING_ID)
    return cut_holes(s, pcd((0, 0), 2 * RING_UP_SCREW_R, 4, 0), H_M3_TAP)


TOWER_TABS = [(-35.0, -23.0), (5.0, 17.0)]   # шипы стоек в поворотный стол (X мира)
TOWER_TNUT_X = -9.0
BRACE_X = (-38.0, -33.0)                     # задняя перемычка между стойками (X мира)
BRACE_Z = (2.0, 24.0)
BRACE_TAB_Z = (12.0, 21.0)
BRACE_SCREW_Z = 7.5


def p04_turntable():
    s = circ((0, 0), TURNTABLE_D / 2, T5)
    s = cut_holes(s, [(0, 0)], NEMA_SHAFT_D + 0.5)
    s = cut_holes(s, pcd((0, 0), CPL_PCD, 4, 45), H_M3)
    s = cut_holes(s, pcd((0, 0), 2 * RING_UP_SCREW_R, 4, 0), H_M3)
    for (y0, y1) in (Y_TWL, Y_TWR):
        for (x0, x1) in TOWER_TABS:
            s = cut_rect(s, x0 - SLOT_CLR / 2, y0 - SLOT_CLR / 2, x1 + SLOT_CLR / 2, y1 + SLOT_CLR / 2)
        s = cut_holes(s, [(TOWER_TNUT_X, (y0 + y1) / 2)], H_M3)
    s = cut_rect(s, -54, -8, -46, 8)          # проход проводов серв вниз
    return s


# ================= СТОЙКИ ПЛЕЧА =================
def sv996_window_holes(shaft, axis_deg=0.0):
    """Окно и 4 отверстия MG996R. axis_deg — направление от вала к дальнему торцу корпуса (к телу)."""
    a = math.radians(axis_deg)
    ux, uy = math.cos(a), math.sin(a)
    vx, vy = -uy, ux
    lo, hi = -SV_SHAFT_OFF - 0.25, (SV_L - SV_SHAFT_OFF) + 0.25
    w = SV_W / 2 + 0.25
    pts = [(shaft[0] + ux * p + vx * q, shaft[1] + uy * p + vy * q) for p, q in ((lo, -w), (hi, -w), (hi, w), (lo, w))]
    mid = (SV_L - 2 * SV_SHAFT_OFF) / 2
    holes = [(shaft[0] + ux * (mid + i * SV_HOLE_SP / 2) + vx * j * SV_HOLE_ACROSS / 2,
              shaft[1] + uy * (mid + i * SV_HOLE_SP / 2) + vy * j * SV_HOLE_ACROSS / 2) for i in (-1, 1) for j in (-1, 1)]
    return pts, holes


def _tower(servo):
    s = hull_plate(T5, circles=[((0, H_SHOULDER), 22.0), ((-36, H_SHOULDER + 8), 8.0)], points=[(-42, 0), (25, 0)])
    for (x0, x1) in TOWER_TABS:
        s = s.union(box2(x0, -T5, x1, 0.01, T5))
    s = tslot(s, (TOWER_TNUT_X, 0.0), (0, 1), T5)
    keeps_c = [((TOWER_TNUT_X, 5), 9.0), (((BRACE_X[0] + BRACE_X[1]) / 2, BRACE_SCREW_Z), 6.0)]
    keeps_p = [grow_rect(BRACE_X[0], BRACE_TAB_Z[0], BRACE_X[1], BRACE_TAB_Z[1], 4.5)]
    if servo:
        pts, holes = sv996_window_holes((0, H_SHOULDER), 180.0)
        s = s.cut(poly(pts, 100, -50))
        s = cut_holes(s, holes, H_M3)
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        keeps_p.append(grow_rect(min(xs), min(ys), max(xs), max(ys), 5.0))
        keeps_c += [(h, 5.5) for h in holes]
    else:
        s = cut_holes(s, [(0, H_SHOULDER)], H_M4P)
        keeps_c.append(((0, H_SHOULDER), 12.0))
        keeps_p.append(rect_pts(-60, H_SHOULDER - 15.0, 40, 120))     # верх сплошной, как у левой стойки
    s = cut_rect(s, BRACE_X[0] - SLOT_CLR / 2, BRACE_TAB_Z[0] - SLOT_CLR / 2, BRACE_X[1] + SLOT_CLR / 2, BRACE_TAB_Z[1] + SLOT_CLR / 2)
    s = cut_holes(s, [((BRACE_X[0] + BRACE_X[1]) / 2, BRACE_SCREW_Z)], H_M3)
    if STYLE in ("B", "C"):
        s = windows(s, 6.0, keeps_c, keeps_p, truss_ribs(-36, 20, 16, 19, 5, 20) if STYLE == "B" else ())
    elif not servo:
        s = s.cut(hull_plate(200, circles=[((-20, 28), 6), ((10, 28), 6)]).translate((0, 0, -100)))
    return s


def p06_tower_l():
    return _tower(True)


def p07_tower_r():
    return _tower(False)


def p08_brace():
    """Локальная X = Y мира, Y = высота над столом."""
    ya, yb = Y_TWR[1], Y_TWL[0]
    s = box2(ya, BRACE_Z[0], yb, BRACE_Z[1], T5)
    s = s.union(box2(yb - 0.01, BRACE_TAB_Z[0], Y_TWL[1], BRACE_TAB_Z[1], T5))
    s = s.union(box2(Y_TWR[0], BRACE_TAB_Z[0], ya + 0.01, BRACE_TAB_Z[1], T5))
    s = tslot(s, (yb, BRACE_SCREW_Z), (-1, 0), T5)
    s = tslot(s, (ya, BRACE_SCREW_Z), (1, 0), T5)
    xm = (ya + yb) / 2
    s = s.cut(hull_plate(20, circles=[((xm - 14, 15), 5), ((xm + 14, 15), 5)]).translate((0, 0, -5)))
    return s


# ================= ПЛЕЧО (5 мм) =================
UA_SPACERS = [(30.0, 0.0), (52.0, 0.0)]
EL_SERVO_PTS, EL_SERVO_HOLES = sv996_window_holes((L1, 0), 180.0)     # корпус MG996R локтя к плечу


def _ua_outline():
    h = UA_HALF_EL
    return hull_plate(T5, circles=[((0, 0), UA_R_SH), ((66, h - 6), 6), ((66, -h + 6), 6),
                                   ((L1 + 14, h - 6), 6), ((L1 + 14, -h + 6), 6)])


def _ua_style(s, keeps_c):
    xs = [p[0] for p in EL_SERVO_PTS]
    keeps_p = [grow_rect(min(xs), -SV_W / 2, max(xs), SV_W / 2, 4.5)]
    return styled(s, keeps_c + [(h, 5.0) for h in EL_SERVO_HOLES], keeps_p, 12, 68, 13, 5.0, waist_h=12.0)


def p09_ua_left():
    s = _ua_outline()
    s = cut_holes(s, [(0, 0)], ACCESS_D)
    s = cut_holes(s, pcd((0, 0), HORN_PCD, 4, 45) + [(L1, 0)] + UA_SPACERS, H_M3)
    return _ua_style(s, [((0, 0), 16.5), ((L1, 0), 7.0)] + [(p, 6.0) for p in UA_SPACERS])


def p10_ua_right():
    s = _ua_outline()
    s = cut_holes(s, [(0, 0)], H_M4P)
    s = s.cut(poly(EL_SERVO_PTS, 100, -50))
    s = cut_holes(s, EL_SERVO_HOLES + UA_SPACERS, H_M3)
    return _ua_style(s, [((0, 0), 16.5)] + [(p, 6.0) for p in UA_SPACERS])


# ================= ПРЕДПЛЕЧЬЕ (3 мм) =================
FA_SPACERS = [(35.0, 0.0), (68.0, 0.0)]


def mg90_window(shaft, axis_ang_deg, near_end_dir=+1):
    """Окно корпуса MG90S и 2 отверстия ушек. axis — направление длинной оси корпуса, near_end_dir: где ближний торец."""
    a = math.radians(axis_ang_deg)
    ux, uy = math.cos(a), math.sin(a)
    vx, vy = -uy, ux
    lo, hi = (-(S_L - S_SHAFT_OFF), S_SHAFT_OFF) if near_end_dir > 0 else (-S_SHAFT_OFF, S_L - S_SHAFT_OFF)
    lo -= 0.2
    hi += 0.2
    w = S_W / 2 + 0.2
    pts = [(shaft[0] + ux * p + vx * q, shaft[1] + uy * p + vy * q) for p, q in ((lo, -w), (hi, -w), (hi, w), (lo, w))]
    mid = (lo + hi) / 2
    holes = [(shaft[0] + ux * (mid + k * S_HOLE_SP / 2), shaft[1] + uy * (mid + k * S_HOLE_SP / 2)) for k in (-1, 1)]
    return pts, holes


PS_PTS, PS_HOLES = mg90_window((L2, 0), 0.0, +1)


def _fa_outline():
    return hull_plate(T3, circles=[((0, 0), FA_R_EL), ((L2, 0), FA_R_TIP)])


def _fa_style(s, keeps_c, keeps_p=()):
    return styled(s, keeps_c + [(p, 5.5) for p in FA_SPACERS], list(keeps_p), 12, 86, 11, 4.5, waist_h=9.5,
                  slot=((44, 0), (58, 0), 6.0))


def p11_forearm_left():
    s = _fa_outline()
    s = cut_holes(s, [(0, 0)] + FA_SPACERS, H_M3)
    s = s.cut(poly(PS_PTS, 100, -50))
    s = cut_holes(s, PS_HOLES, H_M2)
    xs = [p[0] for p in PS_PTS]
    return _fa_style(s, [((0, 0), 7.0)] + [(h, 4.0) for h in PS_HOLES], [grow_rect(min(xs), -6.3, max(xs), 6.3, 4.0)])


def p12_forearm_right():
    s = _fa_outline()
    s = cut_holes(s, [(0, 0)], ACCESS_D)
    s = cut_holes(s, pcd((0, 0), HORN_PCD, 4, 45) + FA_SPACERS + [(L2, 0)], H_M3)
    return _fa_style(s, [((0, 0), 15.0), ((L2, 0), 7.0)])


# ================= КИСТЬ (3 мм) =================
C2_X = (Y_WB[1], Y_WA[0])        # -19…21 (Y мира)
C2_W = (-23.0, 12.0)
C2_TABS_W = [(-20.0, -12.0), (2.0, 10.0)]
C2_SCREW_W = -5.0


def _wrist_side(horn):
    u0 = W_SERVO_PLATE_U
    s = hull_plate(T3, circles=[((0, 0), 12.0)], points=rect_pts(26, -25, u0 + T3 + 3.5, 14))
    for (w0, w1) in C2_TABS_W:
        s = cut_rect(s, u0 - SLOT_CLR / 2, w0 - SLOT_CLR / 2, u0 + T3 + SLOT_CLR / 2, w1 + SLOT_CLR / 2)
    s = cut_holes(s, [(u0 + T3 / 2, C2_SCREW_W)], H_M3)
    if horn:
        s = cut_holes(s, [(0, 0)], 6.0)
        s = cut_holes(s, horn_star((0, 0), a0=45), 1.5)
    else:
        s = cut_holes(s, [(0, 0)], H_M3)
    keeps_c = [((0, 0), 16.0), ((u0 + T3 / 2, C2_SCREW_W), 5.0)]
    keeps_p = [grow_rect(u0 - 0.1, w0 - 0.1, u0 + T3 + 0.1, w1 + 0.1, 3.5) for (w0, w1) in C2_TABS_W]
    if STYLE == "A":
        s = s.cut(circ((17, -8), 4.5, 200, -100))
    else:
        s = windows(s, 4.0, keeps_c, keeps_p, [((14, -14), (30, 8), 4.0)] if STYLE == "B" else (), min_area=15.0, rnd=1.5)
    return s


def p17_wrist_a():
    return _wrist_side(True)


def p18_wrist_b():
    return _wrist_side(False)


def p19_wrist_plate():
    """Локальная X = Y мира (поперёк), локальная Y = w (перпендикуляр к оси клешни в плоскости руки)."""
    xa, xb = C2_X
    s = box2(xa, C2_W[0], xb, C2_W[1], T3)
    for (w0, w1) in C2_TABS_W:
        s = s.union(box2(xb - 0.01, w0, xb + T3, w1, T3)).union(box2(xa - T3, w0, xa + 0.01, w1, T3))
    s = tslot(s, (xb, C2_SCREW_W), (-1, 0), T3)
    s = tslot(s, (xa, C2_SCREW_W), (1, 0), T3)
    pts, holes = mg90_window((0, 0), 90.0, +1)     # длинная ось корпуса вдоль w, ближний торец в +w
    s = s.cut(poly(pts, 100, -50))
    return cut_holes(s, holes, H_M2)


# ================= КЛЕШНЯ (3 мм), система клешни: X поперёк, Y вперёд, Z = w + 12.5 =================
GR, GL = (G_A, 0.0), (-G_A, 0.0)
IR, IL = (G_A + G_VX, G_VY), (-(G_A + G_VX), G_VY)
G_RB = 4.5
G_WARM = 8.0
Y_PALM_REAR = (GB_U + T3) - G_U        # -22: задняя кромка ладони = передняя грань задней плиты
PALM_TABS = [(-16.0, -6.0), (6.0, 16.0)]


def arm_end(phi, side=+1):
    p = math.radians(phi)
    return (side * (G_A + G_L * math.sin(p)), G_L * math.cos(p))


def p20_gripper_back():
    """Локальная X = X клешни, Y = w."""
    s = hull_plate(T3, circles=[((sx * 16, sy), 4.0) for sx in (-1, 1) for sy in (-12.0, 6.0)])
    s = cut_holes(s, [(0, 0)], 6.0)
    horn = [(k * r, 0) for k in (-1, 1) for r in (7, 9, 11, 13)] + [(0, r) for r in (7, 9)]
    s = cut_holes(s, horn, 1.5)
    wp = (-12.5, -12.5 + T3)
    for (x0, x1) in PALM_TABS:
        s = cut_rect(s, x0 - SLOT_CLR / 2, wp[0] - SLOT_CLR / 2, x1 + SLOT_CLR / 2, wp[1] + SLOT_CLR / 2)
    s = cut_holes(s, [(0, wp[0] + T3 / 2)], H_M3)
    return s


def p21_palm():
    yr = Y_PALM_REAR
    s = hull_plate(T3, circles=[(GL, 8.0), (IR, 7.0), (IL, 7.0), ((14, 10), 6.5)],
                   points=rect_pts(-22, yr, 22, yr + 10))
    for (x0, x1) in PALM_TABS:
        s = s.union(box2(x0, yr - T3, x1, yr + 0.01, T3))
    s = tslot(s, (0.0, yr), (0, 1), T3)
    pts, holes = mg90_window(GR, 90.0, +1)         # корпус назад (−Y), вал впереди
    s = s.cut(poly(pts, 100, -50))
    s = cut_holes(s, holes, H_M2)
    return cut_holes(s, [GL, IR, IL], H_M3)


def p22_gear_arm(side):
    G = GR if side > 0 else GL
    F1 = arm_end(G_PHI_C, side)
    tooth0 = 180.0 if side > 0 else 180.0 / G_Z
    s = poly(gear_points(*G, tooth0), T3)
    s = s.union(hull_plate(T3, circles=[(G, G_WARM / 2 + 2), (F1, G_RB)]))
    s = cut_holes(s, [F1], H_M3)
    if side > 0:
        s = cut_holes(s, [G], 2.4)
        u = (math.sin(math.radians(G_PHI_C)), math.cos(math.radians(G_PHI_C)))
        hn = [(G[0] + u[0] * r, G[1] + u[1] * r) for r in (8, 10, 12, 14)] + [(G[0] - u[0] * 8, G[1] - u[1] * 8)]
        s = cut_holes(s, hn, 1.4)
    else:
        s = cut_holes(s, [G], H_M3)
    return s


def p24_link():
    F1 = arm_end(G_PHI_C, +1)
    F2 = (F1[0] + G_VX, F1[1] + G_VY)
    s = hull_plate(T3, circles=[(IR, G_RB), (F2, G_RB)])
    return cut_holes(s, [IR, F2], H_M3)


def _catmull(pts, n=16):
    P = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = [np.array(P[j], float) for j in (i - 1, i, i + 1, i + 2)]
        for k in range(n):
            t = k / n
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(np.array(pts[-1], float))
    return out


G = G_GAP
FINGER = {   # стиль: хвост хребта f(x2, y2, ty), ширина пальца, высота губки
    "A": (lambda x2, y2, ty: [(x2 + 7.5, y2 + 10), (x2 + 6.5, y2 + 21), (G + 10, ty - 2), (G + 3, ty)], 8.0, 16.0),   # крюк
    "B": (lambda x2, y2, ty: [(x2 + 1.0, y2 + 8), (G + 9.5, ty - 12), (G + 5.5, ty - 2), (G + 3, ty)], 9.0, 25.0),   # клык
    "C": (lambda x2, y2, ty: [(x2 + 12, y2 + 10), (x2 + 13, y2 + 25), (x2 + 5, ty - 1), (G + 3, ty)], 7.0, 11.0),   # дуга
}


def finger_geom():
    F1 = arm_end(G_PHI_C, +1)
    F2 = (F1[0] + G_VX, F1[1] + G_VY)
    x2, y2 = F2
    tail, fw, ph = FINGER[FINGER_STYLE]
    ty = y2 + 32.0                         # верх губки
    spine = [F1, F2] + tail(x2, y2, ty)
    return F1, F2, ty, spine


PAD_W = 6.5


def p25_finger():
    """Правый палец в позе «закрыто». Губка с насечкой смотрит в −X (к другому пальцу)."""
    F1, F2, ty, spine = finger_geom()
    _, FW_, PAD_H = FINGER[FINGER_STYLE]
    from shapely.geometry import LineString
    c = _catmull(spine)
    from shapely.geometry import box as sbox
    body = LineString([tuple(p) for p in c]).buffer(FW_ / 2, quad_segs=12, cap_style="round", join_style="round")
    body = body.intersection(sbox(G_GAP, -1e3, 1e3, 1e3))         # губка не заходит за ось симметрии
    s = poly(list(body.exterior.coords)[:-1], T3)
    s = s.union(circ(F1, G_RB + 0.5, T3)).union(circ(F2, G_RB + 0.5, T3))
    pad = hull_plate(T3, circles=[((G_GAP + PAD_W - 2.0, ty + 1.0), 2.0)],
                     points=[(G_GAP, ty + 3.0), (G_GAP, ty - PAD_H), (G_GAP + PAD_W, ty - PAD_H + 2.5), (G_GAP + PAD_W, ty - 3)])
    s = s.union(pad)
    y = ty - PAD_H + 1.5
    while y < ty + 1.0:                      # насечка на губке
        s = s.cut(poly([(G_GAP - 0.01, y), (G_GAP + 1.1, y + 1.25), (G_GAP - 0.01, y + 2.5)], T3 + 2, -1))
        y += 2.5
    return cut_holes(s, [F1, F2], H_M3)


# ================= список =================
def _all_parts():
    return [
        Part("01", "osnovanie_niz", "Основание нижнее", T5, p01_bottom()),
        Part("02", "plita_dvigatelya", "Плита двигателя (верх основания)", T5, p02_top()),
        Part("03", "kolco_nizhnee", "Кольцо-центратор нижнее (51106)", T5, p03_ring_low()),
        Part("04", "povorotny_stol", "Поворотный стол", T5, p04_turntable()),
        Part("05", "kolco_verhnee", "Кольцо-центратор верхнее (резьба M3 метчиком)", T5, p05_ring_up()),
        Part("06", "stoyka_levaya", "Стойка левая (MG996R плеча)", T5, p06_tower_l()),
        Part("07", "stoyka_pravaya", "Стойка правая (ось M4)", T5, p07_tower_r()),
        Part("08", "peremychka", "Задняя перемычка стоек", T5, p08_brace()),
        Part("09", "plecho_levoe", "Плечо левое (на качалке MG996R плеча)", T5, p09_ua_left()),
        Part("10", "plecho_pravoe", "Плечо правое (MG996R локтя)", T5, p10_ua_right()),
        Part("11", "predplechye_levoe", "Предплечье левое (MG90S наклона)", T3, p11_forearm_left()),
        Part("12", "predplechye_pravoe", "Предплечье правое (на качалке локтя)", T3, p12_forearm_right()),
        Part("13", "kist_A", "Кисть A (на качалке наклона)", T3, p17_wrist_a()),
        Part("14", "kist_B", "Кисть B (на оси)", T3, p18_wrist_b()),
        Part("15", "kist_plita", "Плита сервы вращения", T3, p19_wrist_plate()),
        Part("16", "kleshnya_zad", "Задняя плита клешни (на качалке вращения)", T3, p20_gripper_back()),
        Part("17", "ladon", "Ладонь клешни", T3, p21_palm()),
        Part("18", "shesternya_R", "Шестерня-рычаг R ведущая (на качалке)", T3, p22_gear_arm(+1)),
        Part("19", "shesternya_L", "Шестерня-рычаг L ведомая", T3, p22_gear_arm(-1)),
        Part("20", "povodok", "Поводок (левый = правый)", T3, p24_link(), qty=2),
        Part("21", "palec", "Палец (4 одинаковых, левые перевёрнуты)", T3, p25_finger(), qty=4),
    ]


# ================= детали manual берём из STEP, который сохранил SolidWorks =================
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))   # папка roboruka_v1


def part_status():
    """parts.csv: pid;name;module;status;note. status = gen (геометрию строит Python) | manual (правишь в SolidWorks)."""
    st = {}
    path = os.path.join(ROOT, "parts.csv")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for row in csv.DictReader(fh, delimiter=";"):
                st[row["pid"].strip()] = row
    return st


def build_parts():
    parts = _all_parts()
    st = part_status()
    for p in parts:
        row = st.get(p.pid)
        p.status = row["status"].strip() if row else "gen"
        p.module = row["module"].strip() if row else ""
        if p.status == "manual":
            step = os.path.join(ROOT, "step_detali", p.fname + ".step")
            if not os.path.exists(step):
                raise FileNotFoundError(f"{p.fname}: статус manual, но нет {step}. Запусти ExportAll в SolidWorks.")
            p.solid = cq.importers.importStep(step)
    return parts
