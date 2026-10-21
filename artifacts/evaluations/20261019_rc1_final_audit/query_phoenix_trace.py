import urllib.request
import json
import sys
from pathlib import Path

trace_id = "24d6d767c93a54a83754e8f722e82233"
url = "http://127.0.0.1:6006/v1/projects/ouroboros-swarm/spans"

all_spans = []
cursor = None

while True:
    req_url = url
    if cursor:
        req_url += f"?cursor={cursor}"
    req = urllib.request.Request(req_url)
    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            spans_chunk = data.get("data", [])
            for s in spans_chunk:
                if s.get("context", {}).get("trace_id") == trace_id:
                    all_spans.append(s)
            cursor = data.get("next_cursor")
            if not cursor or len(spans_chunk) == 0:
                break
    except Exception as e:
        print(f"Error querying Phoenix: {e}")
        break

print(f"Total matching spans found for trace {trace_id}: {len(all_spans)}")

# Build span mapping
span_by_id = {}
for s in all_spans:
    sid = s.get("context", {}).get("span_id")
    span_by_id[sid] = s

# Hierarchy and parent-child validation
root_spans = []
child_spans = []
unresolved_parents = []

for s in all_spans:
    name = s.get("name")
    sid = s.get("context", {}).get("span_id")
    pid = s.get("parent_id")
    kind = s.get("span_kind")
    status = s.get("status_code")
    
    if pid is None:
        root_spans.append(s)
    else:
        if pid in span_by_id:
            child_spans.append((s, span_by_id[pid]))
        else:
            unresolved_parents.append((s, pid))

print(f"Root spans: {len(root_spans)}")
print(f"Resolved child spans: {len(child_spans)}")
print(f"Unresolved parents: {len(unresolved_parents)}")

evidence = {
    "trace_id": trace_id,
    "queried_span_count": len(all_spans),
    "root_span_count": len(root_spans),
    "child_span_count": len(child_spans),
    "unresolved_parents_count": len(unresolved_parents),
    "collector_endpoint": "http://127.0.0.1:6006/v1/traces",
    "web_ui_url": f"http://127.0.0.1:6006/projects/ouroboros-swarm/traces/{trace_id}",
    "spans": []
}

for s in all_spans:
    attrs = s.get("attributes", {})
    # Sanitize attributes (no secrets, raw prompts)
    safe_attrs = {}
    for k, v in attrs.items():
        if any(secret_term in k.lower() for secret_term in ["key", "secret", "token", "password", "auth"]):
            if "count" in k.lower():
                safe_attrs[k] = v
            else:
                safe_attrs[k] = "[REDACTED]"
        elif k in ["prompt", "raw_prompt", "full_prompt"]:
            safe_attrs[k] = "[REDACTED_PROMPT]"
        else:
            safe_attrs[k] = v
            
    evidence["spans"].append({
        "span_id": s.get("context", {}).get("span_id"),
        "parent_id": s.get("parent_id"),
        "name": s.get("name"),
        "span_kind": s.get("span_kind"),
        "status_code": s.get("status_code"),
        "start_time": s.get("start_time"),
        "end_time": s.get("end_time"),
        "attributes": safe_attrs
    })

out_path = Path("artifacts/evaluations/20261019_rc1_final_audit/phoenix_trace_24d6d767c93a54a83754e8f722e82233.json")
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
print(f"Evidence successfully written to {out_path}")
