"""Выгрузка: STEP деталей, DXF для лазера, раскладки листов, сборки STEP, PDF-чертежи, рендеры.
Запуск: python export.py [папка_вывода]"""
import os, sys, math, collections
import numpy as np
import ezdxf
import cadquery as cq
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Rectangle
from assembly import *

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "out")
for d in ("step_detali", "dxf_laser", "sborka", "chertezhi", "rendery"):
    os.makedirs(os.path.join(OUT, d), exist_ok=True)

PARTS = build_parts()
PD = {p.pid: p for p in PARTS}


def bottom_face(p):
    return max(p.solid.faces("<Z").vals(), key=lambda f: f.Area())


# ---------- STEP и DXF по деталям ----------
for p in PARTS:
    if p.status != "manual":          # STEP manual-деталей пишет SolidWorks (ExportAll), не трогаем
        cq.exporters.export(p.solid, os.path.join(OUT, "step_detali", p.fname + ".step"))
    cq.exporters.export(cq.Workplane("XY").add(bottom_face(p)), os.path.join(OUT, "dxf_laser", p.fname + ".dxf"))
print("step/dxf ok")


# ---------- раскладка на листы (по толщинам) ----------
def nest(thick, width=300.0, gap=4.0):
    doc = ezdxf.new()
    msp = doc.modelspace()
    doc.layers.add("REZ", color=1)
    doc.layers.add("TEXT", color=3)
    x0 = y0 = rowh = 0.0
    items = []
    for p in PARTS:
        if abs(p.t - thick) < 1e-6:
            items += [p] * p.qty
    items.sort(key=lambda p: -p.solid.val().BoundingBox().ylen)
    for p in items:
        f = bottom_face(p)
        bb = f.BoundingBox()
        if x0 + bb.xlen > width:
            x0, y0, rowh = 0.0, y0 + rowh + gap, 0.0
        tmp = f"/tmp/_nest_{p.pid}.dxf"
        cq.exporters.export(cq.Workplane("XY").add(f.translate(cq.Vector(x0 - bb.xmin, y0 - bb.ymin, 0))), tmp)
        for e in ezdxf.readfile(tmp).modelspace():
            e2 = e.copy()
            e2.dxf.layer = "REZ"
            msp.add_entity(e2)
        msp.add_text(p.pid, dxfattribs={"height": 3, "layer": "TEXT"}).set_placement((x0 + 1, y0 + 1))
        x0 += bb.xlen + gap
        rowh = max(rowh, bb.ylen)
    H = y0 + rowh
    doc.saveas(os.path.join(OUT, "dxf_laser", f"00_list_{thick:.0f}mm.dxf"))
    return width, H


sheets = {T3: nest(T3, 300.0), T5: nest(T5, 400.0)}
print("sheets", sheets)

# ---------- модули (подсборки) ----------
HW_MODULE = [("NEMA17", "M1"), ("51106", "M1"), ("stoyka_M3x45", "M1"), ("mufta", "M2"), ("MG996R_plecho", "M2"),
             ("kachalka_plecho", "M2"), ("os_M4", "M2"), ("MG996R_lokot", "M3"), ("kachalka_lokot", "M3"),
             ("stoyka_M3x41", "M3"), ("stoyka_M3x25", "M4"), ("MG90S_naklon", "M4"), ("kachalka_naklon", "M5"),
             ("MG90S_vrashenie", "M5"), ("kachalka_vrashenie", "M6"), ("MG90S_zahvat", "M6"), ("kachalka_zahvat", "M6"),
             ("stoyka_M3x8", "M6")]


def module_of(name):
    if name[:2].isdigit() and PD.get(name[:2]) is not None:
        return getattr(PD[name[:2]], "module", "")[:2]
    for pre, m in HW_MODULE:
        if name.startswith(pre):
            return m
    return ""


# ---------- сборки STEP ----------
for tag, pose in (("HOME", HOME), ("WORK", WORK)):
    items, info = build(pose, PD)
    asm = cq.Assembly(name=f"roboruka_{tag}")
    used = collections.Counter()
    for n, s, c in items:
        used[n] += 1
        nm = n if used[n] == 1 else f"{n}_{used[n]}"
        s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), -90)   # в SolidWorks «вверх» = +Y
        asm.add(cq.Workplane().add(s), name=nm, color=cq.Color(*COL[c]))
    asm.save(os.path.join(OUT, "sborka", f"roboruka_sborka_{tag}.step"))
    if tag == "HOME":                     # подсборки модулей M1…M6 в общей системе координат
        mods = collections.defaultdict(list)
        for n, s, c in items:
            mods[module_of(n)].append((n, s, c))
        for m, its in sorted(mods.items()):
            if not m:
                continue
            sub = cq.Assembly(name=f"modul_{m}")
            used = collections.Counter()
            for n, s, c in its:
                used[n] += 1
                s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), -90)
                sub.add(cq.Workplane().add(s), name=n if used[n] == 1 else f"{n}_{used[n]}", color=cq.Color(*COL[c]))
            sub.save(os.path.join(OUT, "sborka", f"modul_{m}.step"))
print("asm ok")


# ---------- чертежи ----------
def edges2d(face):
    segs = []
    for w in [face.outerWire()] + face.innerWires():
        for e in w.Edges():
            ts = np.linspace(0, 1, 40 if e.geomType() != "LINE" else 2)
            pts = [e.positionAt(t) for t in ts]
            segs.append(([q.x for q in pts], [q.y for q in pts]))
    return segs


def holes_of(face):
    circ_h, other = [], []
    for w in face.innerWires():
        es = w.Edges()
        if len(es) == 1 and es[0].geomType() == "CIRCLE":
            c = es[0].arcCenter()
            circ_h.append((c.x, c.y, 2 * es[0].radius()))
        else:
            bb = w.BoundingBox()
            other.append((bb.xmin, bb.ymin, bb.xmax, bb.ymax))
    return circ_h, other


def dimline(ax, p0, p1, off, txt, horiz=True):
    if horiz:
        y = off
        ax.annotate("", xy=(p0, y), xytext=(p1, y), arrowprops=dict(arrowstyle="<->", lw=0.6))
        ax.plot([p0, p0], [y, y], lw=0)
        ax.text((p0 + p1) / 2, y + 1, txt, ha="center", va="bottom", fontsize=7)
    else:
        x = off
        ax.annotate("", xy=(x, p0), xytext=(x, p1), arrowprops=dict(arrowstyle="<->", lw=0.6))
        ax.text(x - 1, (p0 + p1) / 2, txt, ha="right", va="center", fontsize=7, rotation=90)


def draw_part(pdf, p):
    f = bottom_face(p)
    bb = f.BoundingBox()
    fig = plt.figure(figsize=(11.69, 8.27))
    ax = fig.add_axes([0.05, 0.12, 0.62, 0.8])
    for xs, ys in edges2d(f):
        ax.plot(xs, ys, "k-", lw=0.8)
    ch, oth = holes_of(f)
    for i, (x, y, d) in enumerate(ch):
        ax.plot([x - d * 0.8, x + d * 0.8], [y, y], color="0.5", lw=0.3)
        ax.plot([x, x], [y - d * 0.8, y + d * 0.8], color="0.5", lw=0.3)
    groups = collections.OrderedDict()
    for (x, y, d) in ch:
        groups.setdefault(round(d, 2), []).append((x, y))
    letters = "ABCDEFGHJKLMNP"
    for k, (d, pts) in enumerate(groups.items()):
        for (x, y) in pts:
            ax.text(x + d / 2 + 0.4, y + d / 2 + 0.2, letters[k], fontsize=6, color="tab:red")
    ax.plot(0, 0, "+", color="tab:blue", ms=10)
    ax.text(0.8, 0.8, "0", color="tab:blue", fontsize=7)
    m = max(bb.xlen, bb.ylen) * 0.12 + 4
    dimline(ax, bb.xmin, bb.xmax, bb.ymin - m, f"{bb.xlen:.1f}", True)
    dimline(ax, bb.ymin, bb.ymax, bb.xmin - m, f"{bb.ylen:.1f}", False)
    ax.set_aspect("equal")
    ax.set_xlim(bb.xmin - 2 * m, bb.xmax + m)
    ax.set_ylim(bb.ymin - 2 * m, bb.ymax + m)
    ax.grid(alpha=0.25, lw=0.3)
    ax.tick_params(labelsize=6)
    # таблица
    tx = fig.add_axes([0.69, 0.12, 0.29, 0.8])
    tx.axis("off")
    lines = [f"Деталь {p.pid}: {p.ru}", f"Файл: {p.fname}", f"Оргстекло {p.t:.0f} мм,  кол-во {p.qty}",
             f"Габарит {bb.xlen:.1f} × {bb.ylen:.1f} мм", "Начало координат (синий +) — ось шарнира", "",
             "Отверстия (центры от начала, мм):"]
    for k, (d, pts) in enumerate(groups.items()):
        lines.append(f" {letters[k]}: Ø{d:.1f} × {len(pts)}")
        for (x, y) in pts[:10]:
            lines.append(f"     ({x:7.2f}; {y:7.2f})")
        if len(pts) > 10:
            lines.append("     …")
    if oth:
        lines.append("")
        lines.append("Окна, пазы (габарит X×Y @ центр):")
        for (x0, y0, x1, y1) in oth[:10]:
            lines.append(f" {x1 - x0:5.1f}×{y1 - y0:5.1f} @ ({(x0 + x1) / 2:6.1f}; {(y0 + y1) / 2:6.1f})")
    if p.note:
        lines += ["", p.note]
    tx.text(0, 1, "\n".join(lines), va="top", ha="left", fontsize=7.2, family="DejaVu Sans Mono")
    fig.text(0.05, 0.05, "Роборука 6 DOF, оргстекло, лазерная резка. Разгулов М., Б01-501. Размеры в мм. "
             "Параметры: scripts/params.py", fontsize=7)
    fig.add_artist(Rectangle((0.02, 0.02), 0.96, 0.96, transform=fig.transFigure, fill=False, lw=1))
    pdf.savefig(fig)
    plt.close(fig)


def draw_scheme(pdf):
    """Лист 0: кинематическая схема, вид сбоку, основные размеры."""
    items, info = build(HOME, PD, with_hw=False)
    fig = plt.figure(figsize=(11.69, 8.27))
    ax = fig.add_axes([0.05, 0.08, 0.6, 0.85])
    for n, s, c in items:
        try:
            pr = s.BoundingBox()
        except Exception:
            continue
    # проекция на XZ: силуэты граней
    for n, s, c in items:
        for f in s.Faces():
            nrm = f.normalAt()
            if abs(nrm.y) < 0.9:
                continue
            for e in f.outerWire().Edges():
                ts = np.linspace(0, 1, 16 if e.geomType() != "LINE" else 2)
                pts = [e.positionAt(t) for t in ts]
                ax.plot([q.x for q in pts], [q.z for q in pts], lw=0.4, color="tab:blue" if "acr" in c else "0.3")
    SH, EL, PT = info["SH"], info["EL"], info["PT"]
    ax.plot([SH[0], EL[0], PT[0]], [SH[1], EL[1], PT[1]], "r-o", lw=1.5, ms=4)
    ax.text(SH[0] + 3, SH[1] - 8, f"J2 плечо\nz={SH[1]:.0f}", color="r", fontsize=8)
    ax.text(EL[0] + 3, EL[1] + 3, "J3 локоть", color="r", fontsize=8)
    ax.text(PT[0] + 3, PT[1] + 3, "J4 наклон", color="r", fontsize=8)
    ax.axhline(0, color="k", lw=0.8)
    ax.set_aspect("equal")
    ax.grid(alpha=0.3, lw=0.3)
    ax.set_title("Вид сбоку (поза HOME), мм", fontsize=10)
    tx = fig.add_axes([0.67, 0.08, 0.31, 0.85])
    tx.axis("off")
    L = ["РОБОРУКА 6 DOF — общие данные", "",
         "J1 основание: NEMA17, прямой привод, ±180°", "   упорный подшипник 51106 (30×47×11)",
         "J2 плечо: MG996R на левой стойке", "J3 локоть: MG996R в локте (на правом плече)",
         "J4 наклон кисти: MG90S (в предплечье)", "J5 вращение клешни: MG90S", "J6 захват: MG90S, шестерни m1.5 z16", "",
         f"Плечо L1 = {L1:.0f} мм, предплечье L2 = {L2:.0f} мм",
         f"Ось плеча над столом: {Z_SH:.0f} мм", f"Ось наклона → центр шестерён: {G_U:.0f} мм",
         f"Раскрытие губок: 0.6 … {2 * G_L * (math.sin(math.radians(G_PHI_O)) - math.sin(math.radians(G_PHI_C))) + 2 * G_GAP:.0f} мм",
         f"Стиль звеньев {STYLE}, пальцы {FINGER_STYLE}", "",
         "Раскладка по Y (левый борт +Y), мм:",
         f"  стойка L {Y_TWL}, R {Y_TWR}", f"  плечо L {Y_UAL}, R {Y_UAR}",
         f"  предплечье L {Y_FAL}, R {Y_FAR}", f"  кисть A {Y_WA}, B {Y_WB}", "",
         "Толщины: 5 мм — 01…10; 3 мм — 11…21", f"Лист 3 мм: {sheets[T3][0]:.0f}×{sheets[T3][1]:.0f} мм",
         f"Лист 5 мм: {sheets[T5][0]:.0f}×{sheets[T5][1]:.0f} мм"]
    tx.text(0, 1, "\n".join(L), va="top", fontsize=8, family="DejaVu Sans Mono")
    fig.add_artist(Rectangle((0.02, 0.02), 0.96, 0.96, transform=fig.transFigure, fill=False, lw=1))
    pdf.savefig(fig)
    plt.close(fig)


with PdfPages(os.path.join(OUT, "chertezhi", "00_chertezhi_vse_detali.pdf")) as pdf:
    draw_scheme(pdf)
    for p in PARTS:
        draw_part(pdf, p)
for p in PARTS:
    with PdfPages(os.path.join(OUT, "chertezhi", p.fname + ".pdf")) as pdf:
        draw_part(pdf, p)
print("pdf ok")

# ---------- масса ----------
mass = {p.pid: p.solid.val().Volume() * 1.19e-3 * p.qty for p in PARTS}
print("масса оргстекла, г: %.0f" % sum(mass.values()))
