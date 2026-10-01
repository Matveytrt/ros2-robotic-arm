"""Экспорт для SolidWorks: из каждой детали получаем текстовое описание эскизов (sw/data/*.txt),
плюс params.txt с глобальными переменными. Макрос BuildParts.bas читает эти файлы
и строит нативные SLDPRT с деревом: Eskiz_kontur → Plastina, Eskiz_otverstiya → Otverstiya.

Формат data-файла (мм, градусы не нужны):
  PART <pid> <name>
  THICK <имя переменной T3|T5> <значение>
  STATUS gen|manual
  SKETCH KONTUR            внешний контур + окна/пазы (всё, что не круглое отверстие)
  L x1 y1 x2 y2            отрезок
  A xc yc xs ys xe ye dir  дуга, dir = 1 против часовой, -1 по часовой
  C xc yc r                окружность
  SKETCH OTVERSTIYA        круглые отверстия
  H xc yc r VAR            отверстие; VAR = глобальная переменная диаметра (D_M3, D_M2) или -
  END
"""
import os, sys, csv, math
from parts import *

HOLE_VARS = {round(H_M3, 3): "D_M3", round(H_M2, 3): "D_M2", round(H_M3_TAP, 3): "D_M3_TAP", round(H_M4, 3): "D_M4"}


def fmt(v):
    return f"{v:.5f}".rstrip("0").rstrip(".") if abs(v) > 1e-9 else "0"


def edge_records(e):
    t = e.geomType()
    p0, p1 = e.startPoint(), e.endPoint()
    if t == "LINE":
        if (p0 - p1).Length < 1e-6:
            return []
        return [f"L {fmt(p0.x)} {fmt(p0.y)} {fmt(p1.x)} {fmt(p1.y)}"]
    if t == "CIRCLE":
        c = e.arcCenter()
        r = e.radius()
        if (p0 - p1).Length < 1e-6:
            return [f"C {fmt(c.x)} {fmt(c.y)} {fmt(r)}"]
        m = e.positionAt(0.5)
        cross = (m.x - p0.x) * (p1.y - m.y) - (m.y - p0.y) * (p1.x - m.x)
        d = 1 if cross > 0 else -1
        return [f"A {fmt(c.x)} {fmt(c.y)} {fmt(p0.x)} {fmt(p0.y)} {fmt(p1.x)} {fmt(p1.y)} {d}"]
    # сплайны и прочее: аппроксимация отрезками
    n = 24
    pts = [e.positionAt(i / n) for i in range(n + 1)]
    return [f"L {fmt(a.x)} {fmt(a.y)} {fmt(b.x)} {fmt(b.y)}" for a, b in zip(pts, pts[1:])]


def part_records(p):
    f = max(p.solid.faces("<Z").vals(), key=lambda x: x.Area())
    kontur, holes = [], []
    for e in f.outerWire().Edges():
        kontur += edge_records(e)
    for w in f.innerWires():
        es = w.Edges()
        if len(es) == 1 and es[0].geomType() == "CIRCLE":
            c = es[0].arcCenter()
            r = es[0].radius()
            var = HOLE_VARS.get(round(2 * r, 3), "-")
            holes.append(f"H {fmt(c.x)} {fmt(c.y)} {fmt(r)} {var}")
        else:
            for e in es:
                kontur += edge_records(e)
    return kontur, holes


def read_status(csv_path):
    st = {}
    if os.path.exists(csv_path):
        with open(csv_path, encoding="utf-8") as fh:
            for row in csv.DictReader(fh, delimiter=";"):
                st[row["pid"]] = row["status"].strip()
    return st


def write_params_txt(path):
    rows = [("T3", T3), ("T5", T5), ("D_M3", H_M3), ("D_M2", H_M2), ("D_M3_TAP", H_M3_TAP), ("D_M4", H_M4),
            ("L1", L1), ("L2", L2)]
    with open(path, "w", encoding="ascii", newline="\r\n") as fh:
        for k, v in rows:
            fh.write(f'"{k}" = {fmt(v)}\n')


if __name__ == "__main__":
    root = sys.argv[1]                       # папка roboruka_v1
    sw = os.path.join(root, "solidworks")
    os.makedirs(os.path.join(sw, "data"), exist_ok=True)
    status = read_status(os.path.join(root, "parts.csv"))
    tvar = {T3: "T3", T5: "T5"}
    n = 0
    for p in build_parts():
        st = status.get(p.pid, "gen")
        if st == "manual":
            print("skip manual", p.fname)
            continue
        kontur, holes = part_records(p)
        with open(os.path.join(sw, "data", p.fname + ".txt"), "w", encoding="ascii", newline="\r\n") as fh:
            fh.write(f"PART {p.pid} {p.fname}\nTHICK {tvar[p.t]} {fmt(p.t)}\nSTATUS {st}\n")
            fh.write("SKETCH KONTUR\n" + "\n".join(kontur) + "\n")
            fh.write("SKETCH OTVERSTIYA\n" + "\n".join(holes) + ("\n" if holes else ""))
            fh.write("END\n")
        n += 1
        print(f"{p.fname}: контур {len(kontur)} сегм., отверстий {len(holes)}")
    write_params_txt(os.path.join(sw, "params.txt"))
    print("data:", n)
