import sys, math, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from assembly import *

def tris(shape, tol=0.25):
    v, t = shape.tessellate(tol, 0.4)
    if not t: return np.zeros((0,3,3))
    v = np.array([[p.x, p.y, p.z] for p in v]); return v[np.array(t)]

def draw(ax, items, elev, azim, title, lim=None):
    light = np.array([0.4, -0.3, 0.85]); light /= np.linalg.norm(light)
    AT, AC = [], []
    for n, s, c in items:
        T = tris(s)
        if len(T) == 0: continue
        nn = np.cross(T[:,1]-T[:,0], T[:,2]-T[:,0]); nn /= (np.linalg.norm(nn,axis=1)[:,None]+1e-9)
        sh = 0.45 + 0.55*np.abs(nn@light)
        base = np.array(COL[c][:3])
        AT.append(T); AC.append(np.clip(base[None,:]*sh[:,None],0,1))
    T = np.concatenate(AT); C = np.concatenate(AC)
    ax.add_collection3d(Poly3DCollection(T, facecolors=C, edgecolors="none"))
    pts = T.reshape(-1,3)
    lo, hi = pts.min(0), pts.max(0)
    if lim: lo, hi = np.array(lim[0]), np.array(lim[1])
    ax.set_xlim(lo[0],hi[0]); ax.set_ylim(lo[1],hi[1]); ax.set_zlim(lo[2],hi[2])
    ax.set_box_aspect(tuple(hi-lo)); ax.view_init(elev=elev, azim=azim); ax.set_axis_off(); ax.set_title(title, fontsize=11)

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/claude-0/asm.png"
    views = [(HOME, 20, -60, "Поза HOME, изометрия"), (HOME, 0, -90, "HOME, вид сбоку"), (WORK, 25, -35, "Поза WORK: захват сверху")]
    fig = plt.figure(figsize=(18, 8), dpi=120)
    for i, (pose, el, az, tt) in enumerate(views):
        items, info = build(pose)
        ax = fig.add_subplot(1, 3, i+1, projection="3d")
        draw(ax, items, el, az, tt)
    plt.tight_layout(); plt.savefig(out, bbox_inches="tight")
    print(info)
