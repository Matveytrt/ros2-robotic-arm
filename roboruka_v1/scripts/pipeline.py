"""Один запуск после правок: python pipeline.py
1) sw_export: данные эскизов и params.txt для деталей gen (их строит макрос BuildParts)
2) export: STEP (кроме manual), DXF, раскладки листов, PDF-чертежи, сборка и модули
3) check: проверка столкновений в позах
Детали manual берутся из step_detali/*.step, который сохранил SolidWorks (макрос ExportAll)."""
import os, sys, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
steps = [["sw_export.py", ROOT], ["export.py", ROOT], ["check.py"]]
if "--fast" in sys.argv:
    steps = steps[:2]
for s in steps:
    print("\n=== " + " ".join(s))
    r = subprocess.run([sys.executable, os.path.join(HERE, s[0])] + s[1:], cwd=HERE)
    if r.returncode != 0:
        sys.exit(f"Ошибка на шаге {s[0]}")
print("\nГотово. Дальше: git add -A && git commit")
