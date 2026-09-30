"""Сборка роборуки в заданной позе. Детали из parts.py + упрощённые покупные изделия."""
import math
import cadquery as cq
from parts import *

Z_BOT = 0.0
Z_TOP = T5 + STANDOFF_H                     # 50 низ плиты двигателя
Z_BRG = Z_TOP + T5                          # 55 низ подшипника
Z_TT = Z_BRG + BRG_H                        # 66 низ поворотного стола
Z_TT_TOP = Z_TT + T5                        # 71 верх стола
Z_SH = Z_TT_TOP + H_SHOULDER                # 121 ось плеча

COL = {
    "acr5": (0.12, 0.42, 0.92, 0.80), "acr3": (0.25, 0.58, 1.00, 0.85), "acrG": (0.80, 0.84, 0.95, 0.95),
    "servo": (0.10, 0.10, 0.12, 1.0), "servo996": (0.12, 0.12, 0.16, 1.0), "horn": (0.92, 0.92, 0.92, 1.0),
    "alu": (0.75, 0.76, 0.80, 1.0), "steel": (0.55, 0.56, 0.60, 1.0), "brass": (0.85, 0.70, 0.25, 1.0),
    "nema": (0.18, 0.18, 0.20, 1.0),
}


def servo_model(L, W, off, tab_len, below, tab_t, above, horn_face, horn_d, horn_t=2.0, spline_d=5.0, boss_d=None):
    x0, x1 = -(L - off), off
    mid = (x0 + x1) / 2
    case = cq.Workplane("XY").box(L, W, below + tab_t + above, centered=False).translate((x0, -W / 2, -tab_t - below))
    tabs = cq.Workplane("XY").box(tab_len, W, tab_t, centered=False).translate((mid - tab_len / 2, -W / 2, -tab_t))
    body = case.union(tabs)
    if boss_d:
        body = body.union(circ((0, 0), boss_d / 2, 1.5, above))
    spline = circ((0, 0), spline_d / 2, horn_face - horn_t - above, above)
    horn = circ((0, 0), horn_d / 2, horn_t, horn_face - horn_t)
    return body.union(spline), horn


def mg996():
    return servo_model(SV_L, SV_W, SV_SHAFT_OFF, SV_TAB_LEN, SV_BELOW_TAB, SV_TAB_T, SV_ABOVE_TAB, SV_HORN_FACE, HORN_D, 3.0, 6.0, 12.0)


def mg90():
    b, _ = servo_model(S_L, S_W, S_SHAFT_OFF, S_TAB_LEN, S_BELOW_TAB, S_TAB_T, S_ABOVE_TAB, S_HORN_FACE, 7.0, 2.0, 4.8, 11.5)
    horn = hull_plate(2.0, circles=[((0, 0), 3.6), ((0, 15), 2.2), ((0, -15), 2.2)]).translate((0, 0, S_HORN_FACE - 2.0))
    hub = circ((0, 0), 3.6, S_HORN_FACE - 2.0 - S_ABOVE_TAB - 1.5, S_ABOVE_TAB + 1.5)
    return b, horn.union(hub)


def tube(r_out, r_in, h):
    return circ((0, 0), r_out, h).cut(circ((0, 0), r_in, h + 2, -1))


def hexs(h):
    return cq.Workplane("XY").polygon(6, 5.5 / math.cos(math.pi / 6)).extrude(h).cut(circ((0, 0), 1.6, h + 2, -1))


def nema():
    body = cq.Workplane("XY").box(NEMA_W, NEMA_W, NEMA_L).translate((0, 0, -NEMA_L / 2)).edges("|Z").chamfer(4)
    boss = circ((0, 0), NEMA_BOSS_D / 2, NEMA_BOSS_H)
    shaft = circ((0, 0), NEMA_SHAFT_D / 2, NEMA_SHAFT_L)
    return body.union(boss).union(shaft)


# ---------- вспомогательные векторы ----------
def v_add(*vs):
    return tuple(sum(c) for c in zip(*vs))


def v_mul(v, k):
    return tuple(c * k for c in v)


def dir_xz(ang):
    a = math.radians(ang)
    return (math.cos(a), 0.0, math.sin(a))


def perp_xz(ang):
    a = math.radians(ang)
    return (-math.sin(a), 0.0, math.cos(a))


def arm_plate(solid, pivot_xz, ang, y_face):
    """Плоская деталь руки: локальная X вдоль ang в плоскости XZ, толщина уходит в −Y от y_face."""
    return place(solid, (pivot_xz[0], y_face, pivot_xz[1]), dir_xz(ang), perp_xz(ang))


# ---------- поза ----------
HOME = dict(q1=0.0, a=75.0, b=-5.0, p=-40.0, r=0.0, phi=G_PHI_C)
WORK = dict(q1=25.0, a=60.0, b=-30.0, p=-60.0, r=45.0, phi=45.0)


def build(pose=HOME, P=None, with_hw=True):
    P = P or {p.pid: p for p in build_parts()}
    q1, a, b, pp, rr, phi = (pose[k] for k in ("q1", "a", "b", "p", "r", "phi"))
    fixed, rot = [], []          # (имя, shape, цвет)

    def S(p):
        return P[p].solid

    # ===== основание (не вращается) =====
    fixed.append(("01_osnovanie_niz", place(S("01"), (0, 0, Z_BOT), (1, 0, 0), (0, 1, 0)), "acr5"))
    fixed.append(("02_plita_dvigatelya", place(S("02"), (0, 0, Z_TOP), (1, 0, 0), (0, 1, 0)), "acr5"))
    fixed.append(("03_kolco_nizhnee", place(S("03"), (0, 0, Z_BRG), (1, 0, 0), (0, 1, 0)), "acr5"))
    if with_hw:
        for sx in (-1, 1):
            for sy in (-1, 1):
                fixed.append((f"stoyka_M3x{STANDOFF_H:.0f}", hexs(STANDOFF_H).translate((sx * STANDOFF_POS, sy * STANDOFF_POS, T5)).val(), "brass"))
        fixed.append(("NEMA17", nema().translate((0, 0, Z_TOP)).val(), "nema"))
        lw = tube(BRG_D / 2, BRG_d / 2 + 1.0, BRG_WASHER_T).translate((0, 0, Z_BRG))
        cage = tube(BRG_D / 2 - 3, BRG_d / 2 + 3, BRG_H - 2 * BRG_WASHER_T).translate((0, 0, Z_BRG + BRG_WASHER_T))
        uw = tube(BRG_D / 2, BRG_d / 2, BRG_WASHER_T).translate((0, 0, Z_TT - BRG_WASHER_T))
        fixed += [("51106_nizhnyaya_shayba", lw.val(), "steel"), ("51106_separator", cage.val(), "alu"), ("51106_verhnyaya_shayba", uw.val(), "steel")]

    # ===== поворотная часть =====
    rot.append(("05_kolco_verhnee", place(S("05"), (0, 0, Z_TT - T5), (1, 0, 0), (0, 1, 0)), "acr5"))
    rot.append(("04_povorotny_stol", place(S("04"), (0, 0, Z_TT), (1, 0, 0), (0, 1, 0)), "acr5"))
    if with_hw:
        cpl = circ((0, 0), CPL_FLANGE_D / 2, CPL_FLANGE_T, -CPL_FLANGE_T).union(circ((0, 0), CPL_HUB_D / 2, CPL_HUB_L, -CPL_FLANGE_T - CPL_HUB_L))
        rot.append(("mufta_flanc_5mm", cpl.translate((0, 0, Z_TT)).val(), "brass"))
    # стойки: локальная X = X мира, Y = высота; толщина уходит в −Y от y-грани
    rot.append(("06_stoyka_levaya", place(S("06"), (0, Y_TWL[1], Z_TT_TOP), (1, 0, 0), (0, 0, 1)), "acr5"))
    rot.append(("07_stoyka_pravaya", place(S("07"), (0, Y_TWR[1], Z_TT_TOP), (1, 0, 0), (0, 0, 1)), "acr5"))
    rot.append(("08_peremychka", place(S("08"), (BRACE_X[0], 0, Z_TT_TOP), (0, 1, 0), (0, 0, 1)), "acr5"))

    SH = (0.0, Z_SH)
    EL = (SH[0] + L1 * math.cos(math.radians(a)), SH[1] + L1 * math.sin(math.radians(a)))
    PT = (EL[0] + L2 * math.cos(math.radians(b)), EL[1] + L2 * math.sin(math.radians(b)))
    ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
    cb, sb_ = math.cos(math.radians(b)), math.sin(math.radians(b))
    if with_hw:
        sbody, shorn = mg996()
        # плечо: ушки на наружной грани левой стойки, вал в −Y, корпус назад (−X)
        rot.append(("MG996R_plecho", place(sbody, (0, Y_TWL[1], Z_SH), (1, 0, 0), (0, 0, 1)), "servo996"))
        rot.append(("kachalka_plecho", place(shorn, (0, Y_TWL[1], Z_SH), (1, 0, 0), (0, 0, 1)), "alu"))
        # локоть: ушки на наружной грани правого плеча, вал в +Y, корпус к плечу
        rot.append(("MG996R_lokot", place(sbody, (EL[0], Y_EL_TAB, EL[1]), (ca, 0, sa), (sa, 0, -ca)), "servo996"))
        rot.append(("kachalka_lokot", place(shorn, (EL[0], Y_EL_TAB, EL[1]), (cb, 0, sb_), (sb_, 0, -cb)), "alu"))
        rot.append(("os_M4_plecho", place(tube(2.0, 0.01, Y_UAR[0] - Y_TWR[0] + 4), (0, Y_TWR[0] - 2, Z_SH), (1, 0, 0), (0, 0, -1)), "steel"))
    rot.append(("09_plecho_levoe", arm_plate(S("09"), SH, a, Y_UAL[1]), "acr5"))
    rot.append(("10_plecho_pravoe", arm_plate(S("10"), SH, a, Y_UAR[1]), "acr5"))
    rot.append(("11_predplechye_levoe", arm_plate(S("11"), EL, b, Y_FAL[1]), "acr3"))
    rot.append(("12_predplechye_pravoe", arm_plate(S("12"), EL, b, Y_FAR[1]), "acr3"))
    if with_hw:
        for i, (x, _) in enumerate(UA_SPACERS):
            c = v_add((SH[0], 0, SH[1]), v_mul(dir_xz(a), x))
            rot.append((f"stoyka_M3x{UA_SPACER_L:.1f}_plecho_{i}", place(hexs(UA_SPACER_L), (c[0], Y_UAR[1], c[2]), (1, 0, 0), (0, 0, -1)), "brass"))
        for i, (x, _) in enumerate(FA_SPACERS):
            c = v_add((EL[0], 0, EL[1]), v_mul(dir_xz(b), x))
            rot.append((f"stoyka_M3x25_predpl_{i}", place(hexs(Y_FAL[0] - Y_FAR[1]), (c[0], Y_FAR[1], c[2]), (1, 0, 0), (0, 0, -1)), "brass"))
        pb, ph = mg90()
        rot.append(("MG90S_naklon", place(pb, (PT[0], Y_PS_TAB, PT[1]), (cb, 0, sb_), (sb_, 0, -cb)), "servo"))
    g = b + pp
    ua, uw = dir_xz(g), perp_xz(g)
    P3 = (PT[0], 0.0, PT[1])
    rot.append(("13_kist_A", place(S("13"), (PT[0], Y_WA[1], PT[1]), ua, uw), "acr3"))
    rot.append(("14_kist_B", place(S("14"), (PT[0], Y_WB[1], PT[1]), ua, uw), "acr3"))
    rot.append(("15_kist_plita", place(S("15"), v_add(P3, v_mul(ua, W_SERVO_PLATE_U)), (0, 1, 0), uw), "acr3"))
    if with_hw:
        cb, sb_ = math.cos(math.radians(b)), math.sin(math.radians(b))
        rot.append(("kachalka_naklon", place(ph, (PT[0], Y_PS_TAB, PT[1]), (cb, 0, sb_), (sb_, 0, -cb)).rotate(cq.Vector(PT[0], 0, PT[1]), cq.Vector(PT[0], 1, PT[1]), -pp), "horn"))
        rb, rh = mg90()
        ydir = cross3(ua, uw)
        rot.append(("MG90S_vrashenie", place(rb, v_add(P3, v_mul(ua, W_SERVO_PLATE_U)), uw, ydir), "servo"))

    # ===== клешня (вращается вокруг оси ua на rr) =====
    grip = []
    O = v_add(P3, v_mul(ua, G_U), v_mul(uw, -12.5))
    X_ = (0, -1, 0)

    def gp(solid, z):
        return place(solid, v_add(O, v_mul(uw, z)), X_, ua)
    grip.append(("16_kleshnya_zad", place(S("16"), v_add(P3, v_mul(ua, GB_U + T3)), X_, uw), "acr3"))
    grip.append(("17_ladon", gp(S("17"), 0.0), "acr3"))
    zg = T3 + G_SPACER
    d = phi - G_PHI_C
    gr = S("18").rotate((GR[0], GR[1], 0), (GR[0], GR[1], 1), -d)
    gl = S("19").rotate((GL[0], GL[1], 0), (GL[0], GL[1], 1), d)
    lk = S("20")
    lr = lk.rotate((IR[0], IR[1], 0), (IR[0], IR[1], 1), -d)
    ll = lk.mirror("YZ").rotate((IL[0], IL[1], 0), (IL[0], IL[1], 1), d)
    grip += [("18_shesternya_R", gp(gr, zg), "acrG"), ("19_shesternya_L", gp(gl, zg), "acrG"),
             ("20_povodok_R", gp(lr, zg), "acr3"), ("20_povodok_L", gp(ll, zg), "acr3")]
    fz = [(zg + T3, "verh"), (zg - T3, "niz")]
    for s_, nm in ((+1, "R"), (-1, "L")):
        a0 = arm_end(G_PHI_C, s_)
        a1 = arm_end(phi, s_)
        f = S("21") if s_ > 0 else S("21").mirror("YZ")
        f = f.translate((a1[0] - a0[0], a1[1] - a0[1], 0))
        for z, tag in fz:
            grip.append((f"21_palec_{nm}_{tag}", gp(f, z), "acr5"))
    if with_hw:
        cb_, ch_ = mg90()
        grip.append(("MG90S_zahvat", gp(cb_.translate((GR[0], GR[1], 0)).rotate((GR[0], GR[1], 0), (GR[0], GR[1], 1), 90), 0.0), "servo"))
        grip.append(("kachalka_zahvat", gp(ch_.translate((GR[0], GR[1], 0)).rotate((GR[0], GR[1], 0), (GR[0], GR[1], 1), -d), 0.0), "horn"))
        for i, pnt in enumerate((GL, IR, IL)):
            grip.append((f"stoyka_M3x8_kleshnya_{i}", gp(hexs(G_SPACER).translate((pnt[0], pnt[1], 0)), T3), "brass"))
        grip.append(("kachalka_vrashenie", place(rh, v_add(P3, v_mul(ua, W_SERVO_PLATE_U)), uw, cross3(ua, uw)), "horn"))
    ax0 = cq.Vector(*P3)
    ax1 = cq.Vector(*v_add(P3, ua))
    grip = [(n, (s.val() if isinstance(s, cq.Workplane) else s).rotate(ax0, ax1, rr), c) for n, s, c in grip]
    rot += grip

    out = []
    for n, s, c in fixed:
        out.append((n, s.val() if isinstance(s, cq.Workplane) else s, c))
    for n, s, c in rot:
        s = s.val() if isinstance(s, cq.Workplane) else s
        out.append((n, s.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), q1), c))
    info = dict(SH=SH, EL=EL, PT=PT, gamma=g)
    return out, info
