import sqlite3
import json
from pathlib import Path

source_db = Path("backend/ouroboros.db") if Path("backend/ouroboros.db").exists() else Path("ouroboros.db")
output_json = Path("backend/app/database/seeds/seed_data.json")
output_json.parent.mkdir(parents=True, exist_ok=True)
frontend_json = Path("frontend/src/data/seedData.json")

conn = sqlite3.connect(str(source_db))
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
tables = [r[0] for r in c.fetchall()]

dump = {}
for table in tables:
    c.execute(f"SELECT * FROM {table}")
    rows = c.fetchall()
    dump[table] = [dict(row) for row in rows]
    print(f"Exported {len(rows)} rows from {table}")

conn.close()

with open(output_json, "w", encoding="utf-8") as f:
    json.dump(dump, f, indent=2, default=str)

if frontend_json.parent.exists():
    with open(frontend_json, "w", encoding="utf-8") as f:
        json.dump(dump, f, indent=2, default=str)
    print(f"Updated {frontend_json}")

print(f"\nSuccessfully exported database to {output_json} ({output_json.stat().st_size / 1024:.1f} KB)")
