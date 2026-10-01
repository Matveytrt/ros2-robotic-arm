import sys
from render import *
from moduli import *
PD = {p.pid: p for p in build_parts()}
lay = module_layout(PD, HOME)
fig = plt.figure(figsize=(18, 11), dpi=100)
for i, (mod, comps) in enumerate(lay.items()):
    items = [(c["name"], apply(c["canon"], c["M"]), c["col"]) for c in comps]
    ax = fig.add_subplot(2, 3, i + 1, projection="3d")
    draw(ax, items, 22, -60, mod)
    L = 25
    for v, col in (((L, 0, 0), "r"), ((0, L, 0), "g"), ((0, 0, L), "b")):
        ax.plot([0, v[0]], [0, v[1]], [0, v[2]], color=col, lw=2.5)
    par, j, port, axis = PORTS[mod]
    ax.text2D(0.02, 0.02, f"вход: {j or '—'}   начало = ось входного шарнира (R=X, G=Y, B=Z)", transform=ax.transAxes, fontsize=8)
plt.tight_layout(); plt.savefig(sys.argv[1], bbox_inches="tight")
