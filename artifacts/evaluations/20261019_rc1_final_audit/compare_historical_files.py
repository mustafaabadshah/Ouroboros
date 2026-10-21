import hashlib
import json
from pathlib import Path

files = [
    "artifacts/v0_11/phase5_live_llm_pilot_4tasks.json",
    "artifacts/evaluations/20261018_104036_agent_eval/agent_eval_run.json",
    "artifacts/v0_11/memory_ablation.json"
]

for f in files:
    p = Path(f)
    print("=" * 60)
    print("File:", f)
    if not p.exists():
        print("  DOES NOT EXIST")
        continue
    raw = p.read_bytes()
    print("  Size:", len(raw), "bytes")
    print("  SHA256:", hashlib.sha256(raw).hexdigest())
    try:
        data = json.loads(raw.decode("utf-8"))
        print("  Top-level keys:", list(data.keys()))
        for k in ["run_id", "timestamp", "evaluation_timestamp", "condition", "task_id", "metadata"]:
            if k in data:
                print(f"  {k}:", data[k])
    except Exception as e:
        print("  JSON parse error:", e)
