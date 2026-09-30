import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from parts import *
def outline(part):
    f = max(part.solid.faces("<Z").vals(), key=lambda x: x.Area())
    segs=[]
    for w in [f.outerWire()]+f.innerWires():
        for e in w.Edges():
            pts=[e.positionAt(t) for t in np.linspace(0,1,24)]
            segs.append(([p.x for p in pts],[p.y for p in pts]))
    return segs
if __name__=="__main__":
    import sys
    P=build_parts()
    sel = sys.argv[1].split(",") if len(sys.argv)>1 else None
    P=[p for p in P if sel is None or p.pid in sel]
    n=len(P); cols=min(5,n); rows=(n+cols-1)//cols
    fig,axs=plt.subplots(rows,cols,figsize=(4*cols,4*rows),squeeze=False)
    for ax in axs.flat: ax.axis("off")
    for ax,p in zip(axs.flat,P):
        for xs,ys in outline(p): ax.plot(xs,ys,'k-',lw=0.6)
        ax.set_aspect("equal"); ax.set_title(f"{p.pid} {p.name}",fontsize=8); ax.axis("on"); ax.grid(alpha=.3)
    plt.tight_layout(); plt.savefig("/tmp/claude-0/prev.png",dpi=110)
