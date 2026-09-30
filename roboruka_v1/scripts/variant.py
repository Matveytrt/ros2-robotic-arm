import sys, os
from render import *
from preview2d import outline
tag = sys.argv[1]; out = sys.argv[2]
names = {"A": "A — «как на фото»: сплошные, вогнутые бока", "B": "B — «ферма»: треугольные окна", "C": "C — «рамка»: большие окна"}
fn = {"A": "крюк", "B": "клык, длинная губка", "C": "дуга, круглый карман"}
fig = plt.figure(figsize=(20, 7.2), dpi=100)
items, _ = build(HOME)
ax = fig.add_subplot(1, 3, 1, projection="3d"); draw(ax, items, 18, -62, "Вариант " + names[STYLE])
keys = ("11_","12_","13_","14_","15_","16_","17_","18_","19_","20_","21_","MG90S","kachalka_n","kachalka_v","kachalka_z","stoyka_M3x8","stoyka_M3x25")
items, _ = build(dict(q1=0, a=75, b=0, p=0, r=0, phi=40))
items = [it for it in items if it[0].startswith(keys)]
ax = fig.add_subplot(1, 3, 2, projection="3d"); draw(ax, items, 32, -48, "Кисть и клешня, пальцы: " + fn[FINGER_STYLE])
P = {p.pid: p for p in build_parts()}
ax = fig.add_subplot(1, 3, 3)
layout = [("10", 0, 0), ("09", 0, -45), ("12", 0, -90), ("11", 0, -125), ("06", 0, -215), ("13", 90, -215), ("21", 160, -250)]
for pid, dx, dy in layout:
    for xs, ys in outline(P[pid]):
        ax.plot([x + dx for x in xs], [y + dy for y in ys], "k-", lw=0.6)
    ax.text(dx - 25, dy, pid, fontsize=8, color="tab:blue")
ax.set_aspect("equal"); ax.axis("off"); ax.set_title("10/09 плечо, 12/11 предплечье, 06 стойка, 13 кисть, 21 палец", fontsize=9)
plt.tight_layout(); plt.savefig(out, bbox_inches="tight")
