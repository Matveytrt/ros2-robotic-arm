import itertools, sys
from assembly import *
import params
POSES = {
 "lokot_slozhen": dict(q1=0, a=80, b=-130, p=0, r=0, phi=G_PHI_C),
 "lokot_vytyanut": dict(q1=0, a=30, b=30, p=0, r=0, phi=G_PHI_O),
 "nazad_vniz": dict(q1=0, a=120, b=-100, p=-60, r=0, phi=G_PHI_C),
 "HOME": HOME,
 "WORK": dict(q1=0, a=60, b=-30, p=-60, r=45, phi=45),
 "vytyanuta": dict(q1=0, a=40, b=0, p=0, r=0, phi=G_PHI_O),
 "slozhena": dict(q1=0, a=110, b=-25, p=-70, r=90, phi=G_PHI_C),
 "nizko": dict(q1=0, a=40, b=-60, p=-30, r=-60, phi=30),
 "kist+90": dict(q1=0, a=75, b=-5, p=90, r=90, phi=G_PHI_O),
 "kist-90": dict(q1=0, a=75, b=-5, p=-90, r=-90, phi=G_PHI_O),
 "kist+110": dict(q1=0, a=75, b=-5, p=110, r=0, phi=G_PHI_C),
 "vverh": dict(q1=0, a=95, b=55, p=60, r=0, phi=G_PHI_O),
}
def run(names=None):
    P = {p.pid: p for p in build_parts()}
    res = {}
    for pn, pose in POSES.items():
        if names and pn not in names: continue
        items, _ = build(pose, P)
        bbs = [s.BoundingBox() for _, s, _ in items]
        bad = []
        for i, j in itertools.combinations(range(len(items)), 2):
            a, b = bbs[i], bbs[j]
            if a.xmax < b.xmin or b.xmax < a.xmin or a.ymax < b.ymin or b.ymax < a.ymin or a.zmax < b.zmin or b.zmax < a.zmin: continue
            try:
                v = items[i][1].intersect(items[j][1]).Volume()
            except Exception as e:
                v = -1
            if v > 0.5 or v < 0:
                bad.append((items[i][0], items[j][0], round(v, 1)))
        res[pn] = bad
        print(f"== {pn}: {len(bad)}"); [print("   ", b) for b in bad]
        sys.stdout.flush()
    return res
if __name__ == "__main__":
    run(sys.argv[1:] or None)
