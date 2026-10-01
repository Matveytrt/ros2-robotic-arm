"""
МОДУЛИ И ИНТЕРФЕЙСЫ РОБОРУКИ: единственное место, где описано, как модули стыкуются.

У каждого модуля своя система координат (СК), начало координат стоит на его входном шарнире.
Интерфейс (порт) = точка и ось шарнира в СК родителя. Шесть строк таблицы PORTS ниже —
вот и весь интерфейс между модулями. Внутри модуля можно менять что угодно,
пока порт остаётся на месте.

Та же таблица потом станет URDF для ROS2: модуль = link, порт = joint.

Запуск: python moduli.py <папка roboruka_v1>
  sborka/moduli/M*.step       модули, каждый в своей СК
  solidworks/moduli/M*.txt     состав модулей для макроса BuildAssembly
  solidworks/moduli/roboruka.txt
  solidworks/pokupnye/*.step   покупные изделия (серво, NEMA17, подшипник, стойки)
"""
import os, sys, math, collections
import numpy as np
import cadquery as cq
from assembly import *

# ---------------- ИНТЕРФЕЙСЫ ----------------
# модуль: (родитель, шарнир, порт в СК родителя [мм], ось шарнира в СК родителя)
PORTS = collections.OrderedDict([
    ("M1_osnovanie",   (None,             None, None,                    None)),
    ("M2_platforma",   ("M1_osnovanie",   "J1", (0.0, 0.0, Z_TT),        (0, 0, 1))),
    ("M3_plecho",      ("M2_platforma",   "J2", (0.0, 0.0, Z_SH - Z_TT), (0, -1, 0))),
    ("M4_predplechye", ("M3_plecho",      "J3", (L1, 0.0, 0.0),          (0, -1, 0))),
    ("M5_kist",        ("M4_predplechye", "J4", (L2, 0.0, 0.0),          (0, -1, 0))),
    ("M6_kleshnya",    ("M5_kist",        "J5", (GB_U, 0.0, 0.0),        (1, 0, 0))),
])
# Положительный угол: J1 против часовой сверху, J2/J3/J4 поднимают звено, J5 по правилу правой руки вокруг оси клешни.
# J6 (захват) живёт внутри M6: угол рычага шестерни G_PHI_C…G_PHI_O.


def joints_from_pose(pose):
    """Позу assembly.py (углы звеньев к горизонту) переводим в углы шарниров."""
    return {"J1": pose["q1"], "J2": pose["a"], "J3": pose["b"] - pose["a"], "J4": pose["p"], "J5": pose["r"]}


# ---------------- однородные матрицы ----------------
def T(t):
    m = np.eye(4)
    m[:3, 3] = t
    return m


def R(axis, deg):
    a = np.array(axis, float)
    a /= np.linalg.norm(a)
    th = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    m = np.eye(4)
    m[:3, :3] = np.eye(3) + math.sin(th) * K + (1 - math.cos(th)) * K @ K
    return m


def frames(q):
    """Прямая кинематика: СК каждого модуля в мировой СК (Z вверх)."""
    F = {}
    for m, (par, j, port, axis) in PORTS.items():
        F[m] = np.eye(4) if par is None else F[par] @ T(port) @ R(axis, q[j])
    return F


# ---------------- к какому модулю относится компонент ----------------
# Качалка серво едет вместе с ведомым звеном, поэтому относится к модулю-ребёнку.
HW = [("NEMA17", "M1_osnovanie", "NEMA17"), ("51106_nizhnyaya", "M1_osnovanie", "51106_shayba_niz"),
      ("51106_separator", "M1_osnovanie", "51106_separator"), ("stoyka_M3x45", "M1_osnovanie", "stoyka_M3x45"),
      ("51106_verhnyaya", "M2_platforma", "51106_shayba_verh"), ("mufta", "M2_platforma", "mufta_flanc_5mm"),
      ("MG996R_plecho", "M2_platforma", "MG996R"), ("os_M4", "M2_platforma", "os_M4"),
      ("kachalka_plecho", "M3_plecho", "kachalka_MG996R"), ("MG996R_lokot", "M3_plecho", "MG996R"),
      ("stoyka_M3x41", "M3_plecho", "stoyka_M3x41_5"),
      ("kachalka_lokot", "M4_predplechye", "kachalka_MG996R"), ("stoyka_M3x25", "M4_predplechye", "stoyka_M3x25"),
      ("MG90S_naklon", "M4_predplechye", "MG90S"),
      ("kachalka_naklon", "M5_kist", "kachalka_MG90S"), ("MG90S_vrashenie", "M5_kist", "MG90S"),
      ("kachalka_vrashenie", "M6_kleshnya", "kachalka_MG90S"), ("MG90S_zahvat", "M6_kleshnya", "MG90S"),
      ("kachalka_zahvat", "M6_kleshnya", "kachalka_MG90S"), ("stoyka_M3x8", "M6_kleshnya", "stoyka_M3x8")]


def canon_hw():
    """Покупные изделия в собственной СК: из этих форм сделаны их файлы."""
    b996, h996 = mg996()
    b90, h90 = mg90()
    return {
        "MG996R": b996, "kachalka_MG996R": h996, "MG90S": b90, "kachalka_MG90S": h90, "NEMA17": nema(),
        "51106_shayba_niz": tube(BRG_D / 2, BRG_d / 2 + 1.0, BRG_WASHER_T),
        "51106_separator": tube(BRG_D / 2 - 3, BRG_d / 2 + 3, BRG_H - 2 * BRG_WASHER_T),
        "51106_shayba_verh": tube(BRG_D / 2, BRG_d / 2, BRG_WASHER_T),
        "mufta_flanc_5mm": circ((0, 0), CPL_FLANGE_D / 2, CPL_FLANGE_T, -CPL_FLANGE_T).union(
            circ((0, 0), CPL_HUB_D / 2, CPL_HUB_L, -CPL_FLANGE_T - CPL_HUB_L)),
        "os_M4": tube(2.0, 0.01, Y_UAR[0] - Y_TWR[0] + 4),
        "stoyka_M3x45": hexs(STANDOFF_H), "stoyka_M3x41_5": hexs(UA_SPACER_L),
        "stoyka_M3x25": hexs(Y_FAL[0] - Y_FAR[1]), "stoyka_M3x8": hexs(G_SPACER),
    }


def classify(name, PD):
    if name[:2].isdigit() and name[2] == "_":
        p = PD[name[:2]]
        return p.module, ("part", p.fname), p.solid.val(), p.t
    for pre, mod, key in HW:
        if name.startswith(pre):
            return mod, ("hw", key), None, None
    raise KeyError(name)


# ---------------- жёсткое преобразование по вершинам (Кабш) ----------------
def verts(shape):
    return np.array([[v.X, v.Y, v.Z] for v in shape.Vertices()])


def rigid(P, Q):
    """Кабш: собственное вращение + сдвиг, переводящие точки P в Q (порядок точек совпадает)."""
    cp, cq_ = P.mean(0), Q.mean(0)
    H = (P - cp).T @ (Q - cq_)
    U, _, Vt = np.linalg.svd(H)
    D = np.diag([1, 1, np.sign(np.linalg.det(Vt.T @ U.T))])
    Rm = Vt.T @ D @ U.T
    M = np.eye(4)
    M[:3, :3] = Rm
    M[:3, 3] = cq_ - Rm @ cp
    return M


def flip(t):
    """Плоская деталь, перевёрнутая другой стороной: поворот на 180° вокруг Y + сдвиг на толщину."""
    return T((0, 0, t)) @ R((0, 1, 0), 180)


MIRROR_X = np.diag([-1.0, 1.0, 1.0, 1.0])


def world_transform(canon, placed, thick):
    """Матрица «деталь в своей СК → положение в сборке». Зеркальная копия плоской детали = та же деталь,
    перевёрнутая другой стороной (так её и ставим: отдельный файл не нужен)."""
    P, Q = verts(canon), verts(placed)
    if len(P) != len(Q):
        raise ValueError("разное число вершин")
    cand = [(np.eye(4), np.eye(4))] + ([(MIRROR_X, flip(thick))] if thick else [])
    for fit, real in cand:
        Pp = (fit[:3, :3] @ P.T).T
        M = rigid(Pp, Q)
        err = np.abs((M[:3, :3] @ Pp.T).T + M[:3, 3] - Q).max()
        if err < 1e-4:
            return M @ real
    raise ValueError("не нашлось жёсткого преобразования")


def loc(M):
    from OCP.gp import gp_Trsf
    t = gp_Trsf()
    t.SetValues(*[float(M[i][j]) for i in range(3) for j in range(4)])
    return cq.Location(t)


def apply(shape, M):
    return shape.moved(loc(M))


# ---------------- состав модулей ----------------
def module_layout(PD, pose=HOME):
    """Для каждого компонента: модуль, файл, матрица в СК модуля."""
    items, _ = build(pose, PD)
    F = frames(joints_from_pose(pose))
    hw = canon_hw()
    out = collections.OrderedDict((m, []) for m in PORTS)
    for name, shp, col in items:
        mod, (kind, key), canon, thick = classify(name, PD)
        if kind == "hw":
            canon = hw[key].val() if isinstance(hw[key], cq.Workplane) else hw[key]
        Mw = world_transform(canon, shp, thick)
        Ml = np.linalg.inv(F[mod]) @ Mw
        out[mod].append(dict(name=name, kind=kind, key=key, M=Ml, col=col, canon=canon))
    return out


SYMMETRIC = ("51106", "kachalka_MG996R", "stoyka_", "os_M4", "mufta")   # тела вращения: поворот вокруг своей оси не важен


def check_interfaces(PD, layout, pose):
    """Собираем руку из модулей через PORTS в другой позе и сравниваем с assembly.build:
    проверка, что модули честно стыкуются по портам."""
    items, _ = build(pose, PD)
    F = frames(joints_from_pose(pose))
    world = collections.defaultdict(list)
    for n, s, _ in items:
        world[n].append(s)
    worst = 0.0
    for mod, comps in layout.items():
        for c in comps:
            if pose["phi"] != HOME["phi"] and c["name"].startswith(("18_", "19_", "20_", "21_", "kachalka_zahvat")):
                continue               # J6 внутри модуля
            M = F[mod] @ c["M"]
            P = verts(c["canon"])
            Pm = (M[:3, :3] @ P.T).T + M[:3, 3]
            com = cq.Shape.centerOfMass(apply(c["canon"], M))
            best = 1e9
            for w in world[c["name"]]:
                Q = verts(w)
                d = np.sqrt(((Pm[:, None, :] - Q[None, :, :]) ** 2).sum(-1)).min(1).max()
                if d > 1e-3 and c["key"].startswith(SYMMETRIC):
                    d = (com - cq.Shape.centerOfMass(w)).Length
                best = min(best, d)
            if best > 1e-3:
                print("  не совпал:", c["name"], round(best, 3))
            worst = max(worst, best)
    return worst


# ---------------- выгрузка ----------------
UP = R((1, 0, 0), -90)          # в SolidWorks «вверх» = +Y


def sw_line(prefix, path, M):
    """Строка для макроса: путь и матрица (строки = куда идут оси X, Y, Z детали; сдвиг в мм)."""
    r = M[:3, :3].T.reshape(-1)          # строка i = образ i-й оси
    t = M[:3, 3]
    return prefix + " " + path + " " + " ".join(f"{v:.9f}" for v in r) + " " + " ".join(f"{v:.5f}" for v in t)


def export(root):
    PD = {p.pid: p for p in build_parts()}
    layout = module_layout(PD, HOME)
    pose2 = dict(WORK)
    pose2["phi"] = HOME["phi"]
    err = check_interfaces(PD, layout, pose2)
    print(f"проверка интерфейсов в позе WORK: макс. расхождение {err:.2e} мм")
    assert err < 1e-3, "модули не стыкуются по портам!"

    d_step = os.path.join(root, "sborka", "moduli")
    d_sw = os.path.join(root, "solidworks", "moduli")
    d_hw = os.path.join(root, "solidworks", "pokupnye")
    for d in (d_step, d_sw, d_hw):
        os.makedirs(d, exist_ok=True)
    hw = canon_hw()
    for k, s in hw.items():
        cq.exporters.export(s if isinstance(s, cq.Workplane) else cq.Workplane().add(s), os.path.join(d_hw, k + ".step"))

    F = frames(joints_from_pose(HOME))
    top = []
    for mod, comps in layout.items():
        asm = cq.Assembly(name=mod)
        lines = [f"# {mod}: module frame, origin on input joint. C file r11..r33 tx ty tz (mm)"]
        used = collections.Counter()
        for c in comps:
            used[c["name"]] += 1
            nm = c["name"] if used[c["name"]] == 1 else f'{c["name"]}_{used[c["name"]]}'
            asm.add(cq.Workplane().add(apply(c["canon"], c["M"])), name=nm, color=cq.Color(*COL[c["col"]]))
            path = f'parts\\{c["key"]}.SLDPRT' if c["kind"] == "part" else f'pokupnye\\{c["key"]}.SLDPRT'
            lines.append(sw_line("C", path, c["M"]))
        asm.save(os.path.join(d_step, f"{mod}.step"))
        with open(os.path.join(d_sw, f"{mod}.txt"), "w", encoding="ascii", newline="\r\n") as fh:
            fh.write("\n".join(lines) + "\n")
        top.append(sw_line("C", f"moduli\\{mod}.SLDASM", UP @ F[mod]))
        print(f"{mod}: {len(comps)} комп.")
    with open(os.path.join(d_sw, "roboruka.txt"), "w", encoding="ascii", newline="\r\n") as fh:
        fh.write("# top assembly of modules, pose HOME, Y up\n" + "\n".join(top) + "\n")


if __name__ == "__main__":
    export(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), ".."))
