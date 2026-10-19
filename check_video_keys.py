import glob
import re

keys = set()
for path in glob.glob("*.py"):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    for m in re.finditer(r'(?:video|v|item|v_item)\["([a-zA-Z0-9_]+)"\]', content):
        keys.add(m.group(1))
    for m in re.finditer(r'(?:video|v|item|v_item)\.get\(["\']([a-zA-Z0-9_]+)["\']', content):
        keys.add(m.group(1))

print("Keys accessed on video dicts:")
for k in sorted(keys):
    print(f" - {k}")
