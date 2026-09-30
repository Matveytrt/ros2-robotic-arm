import sys
from render import *
out = sys.argv[1]
keys = ("11_","12_","13_","14_","15_","16_","17_","18_","19_","20_","21_","22_","23_","24_","MG90S","kachalka_n","kachalka_v","kachalka_z","stoyka_M3x8","stoyka_M3x25")
fig = plt.figure(figsize=(18, 7), dpi=120)
for i,(phi,r,tt) in enumerate(((G_PHI_C,0,"Клешня закрыта"),(G_PHI_O,0,"Открыта, зев ≈51 мм"),(G_PHI_O,90,"Вращение 90°"))):
    items, _ = build(dict(q1=0,a=75,b=0,p=0,r=r,phi=phi))
    items = [it for it in items if it[0].startswith(keys)]
    ax = fig.add_subplot(1,3,i+1,projection="3d"); draw(ax, items, 30, -50, tt)
plt.tight_layout(); plt.savefig(out, bbox_inches="tight")
