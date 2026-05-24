import json, os

path = "story_bible.json"
if not os.path.exists(path):
    print("No story bible yet")
    exit()

with open(path) as f:
    b = json.load(f)

print(f"Title: {b['title']}")
print(f"Genre: {b['genre']}")
print()
print("--- WORLD ---")
ws = b.get("world", {}).get("setting", "")
if ws:
    print(ws[:300] + "...")
print(f"System: {b.get('world', {}).get('system_name', 'N/A')}")
print()
print("--- MC ---")
p = b.get("characters", {}).get("protagonist", {})
print(f"Name: {p.get('name', '?')}, Age: {p.get('age', '?')}, Rank: {p.get('initial_rank', '?')}")
print(f"Growth: {' -> '.join([g.split('—')[0].strip() for g in p.get('powers_growth', [])])}")
print()
print("--- CHARACTERS ---")
for role, ch in b.get("characters", {}).items():
    if role in ("system_ui", "protagonist"):
        continue
    if isinstance(ch, list):
        for c in ch:
            print(f"  {c.get('name', '?')} ({c.get('role', '?')})")
    elif isinstance(ch, dict):
        print(f"  {ch.get('name', '?')} ({ch.get('role', '?')})")
print()
print("--- CHAPTERS ---")
for ch in b.get("chapters", []):
    print(f"  Ch {ch['number']}: '{ch['title']}' (~{ch.get('estimated_duration_minutes', '?')}min)")
