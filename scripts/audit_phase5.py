import json
import statistics
import math
from pathlib import Path

data = json.loads(Path("artifacts/v0_11/phase5_live_llm_pilot_4tasks.json").read_text(encoding="utf-8"))

mem_trial = data["raw_trials"]["memory_enabled_trials"][0]
base_trial = data["raw_trials"]["baseline_trials"][0]
mem_tasks = mem_trial["task_results"]
base_tasks = base_trial["task_results"]

print("=== 1. BASIC COUNTS & METRICS ===")
print(f"Total tasks evaluated: {len(mem_tasks)}")
print(f"Eligible tasks: {mem_trial['eligible_tasks']}")
print(f"Adversarial tasks: {mem_trial['adversarial_tasks']}")
print(f"Repairs passed (Flywheel): {mem_trial['repairs_passed']} / {mem_trial['eligible_tasks']} ({mem_trial['eligible_repair_success_rate']*100:.1f}%)")
print(f"Repairs passed (Naive): {base_trial['repairs_passed']} / {base_trial['eligible_tasks']} ({base_trial['eligible_repair_success_rate']*100:.1f}%)")

print("\n=== 2. ATTEMPTS AUDIT ===")
mem_attempts = [t["attempts_executed"] for t in mem_tasks]
base_attempts = [t["attempts_executed"] for t in base_tasks]
print(f"Flywheel attempts: {mem_attempts} -> Mean across all tasks: {sum(mem_attempts)/len(mem_attempts):.2f}")
print(f"Flywheel attempts on passed tasks: {[t['attempts_executed'] for t in mem_tasks if t['passed']]} -> Mean: {sum(t['attempts_executed'] for t in mem_tasks if t['passed'])/sum(1 for t in mem_tasks if t['passed']):.2f}")
print(f"Naive attempts: {base_attempts} -> Mean across all tasks: {sum(base_attempts)/len(base_attempts):.2f}")
print(f"Naive attempts on passed tasks: {[t['attempts_executed'] for t in base_tasks if t['passed']]} -> Mean: {sum(t['attempts_executed'] for t in base_tasks if t['passed'])/sum(1 for t in base_tasks if t['passed']):.2f}")

print("\n=== 3. LATENCY AUDIT ===")
mem_dur = [t["duration_ms"] for t in mem_tasks]
base_dur = [t["duration_ms"] for t in base_tasks]
print(f"Flywheel durations: {sorted(mem_dur)}")
print(f"  Codebase p50 (durations[4//2] = durations[2]): {sorted(mem_dur)[len(mem_dur)//2]}")
print(f"  Standard mathematical median: {statistics.median(mem_dur):.1f}")
print(f"  Arithmetic mean: {statistics.mean(mem_dur):.1f}")

print(f"Naive durations: {sorted(base_dur)}")
print(f"  Codebase p50 (durations[4//2] = durations[2]): {sorted(base_dur)[len(base_dur)//2]}")
print(f"  Standard mathematical median: {statistics.median(base_dur):.1f}")
print(f"  Arithmetic mean: {statistics.mean(base_dur):.1f}")

print("\n=== 4. TOKEN CONSUMPTION & COST AUDIT ===")
mem_in = sum(t["tokens_in"] for t in mem_tasks)
mem_out = sum(t["tokens_out"] for t in mem_tasks)
base_in = sum(t["tokens_in"] for t in base_tasks)
base_out = sum(t["tokens_out"] for t in base_tasks)

print(f"Flywheel: In={mem_in}, Out={mem_out}, Total={mem_in+mem_out}")
print(f"Naive:    In={base_in}, Out={base_out}, Total={base_in+base_out}")
print(f"Overall:  In={mem_in+base_in}, Out={mem_out+base_out}, Total={mem_in+mem_out+base_in+base_out}")
print(f"Invoiced API cost: $0.00 USD (developer tier / free quota)")

print("\n=== 5. PAIRED CONCORDANCE & EXACT TEST ===")
paired = []
for m, b in zip(mem_tasks, base_tasks):
    assert m["task_id"] == b["task_id"]
    tid = m["task_id"]
    paired.append((tid, m["passed"], b["passed"]))
    print(f"Task {tid}: Flywheel={'PASS' if m['passed'] else 'FAIL'} vs Naive={'PASS' if b['passed'] else 'FAIL'}")

# Concordance cells:
# a = Flywheel Pass & Naive Pass
# b = Flywheel Pass & Naive Fail
# c = Flywheel Fail & Naive Pass
# d = Flywheel Fail & Naive Fail
a = sum(1 for _, m_p, b_p in paired if m_p and b_p)
b = sum(1 for _, m_p, b_p in paired if m_p and not b_p)
c = sum(1 for _, m_p, b_p in paired if not m_p and b_p)
d = sum(1 for _, m_p, b_p in paired if not m_p and not b_p)

print(f"\n2x2 Table: a={a} (ties pass), b={b} (Flywheel win), c={c} (Naive win), d={d} (ties fail)")
n_discordant = b + c
if n_discordant > 0:
    # Binomial exact test (two-tailed McNemar exact):
    # Under H0: b ~ Binomial(n_discordant, 0.5)
    # One-tailed p = P(X >= b)
    p_one_tailed = sum(math.comb(n_discordant, k) * (0.5 ** n_discordant) for k in range(b, n_discordant + 1))
    p_two_tailed = min(1.0, 2.0 * p_one_tailed)
    print(f"McNemar Exact Test (N={len(paired)}, discordant={n_discordant}): one-tailed p={p_one_tailed:.4f}, two-tailed p={p_two_tailed:.4f}")

print("\n=== 6. PER-TASK COLD ATTEMPT & DIAGNOSTIC AUDIT ===")
for m, b in zip(mem_tasks, base_tasks):
    tid = m["task_id"]
    print(f"\n--- {tid} ---")
    m_h1 = m["history"][0]
    b_h1 = b["history"][0]
    print(f"Attempt 1 Flywheel: verdict={m_h1.get('verdict')}, acc={m_h1.get('acceptance_passed')}, reg={m_h1.get('regression_passed')}")
    print(f"Attempt 1 Naive:    verdict={b_h1.get('verdict')}, acc={b_h1.get('acceptance_passed')}, reg={b_h1.get('regression_passed')}")
    
    # Detailed attempt failure traces
    for i, h in enumerate(m["history"]):
        print(f"  Flywheel Att {i+1}: verdict={h.get('verdict')}, esc={h.get('escalated_plan', False)}")
        if "failures" in h:
            for f in h["failures"]:
                tb = f.get("traceback", "")
                for line in tb.splitlines():
                    if "E   " in line or "AssertionError" in line:
                        print(f"    Flywheel failure: {line.strip()}")
    for i, h in enumerate(b["history"]):
        print(f"  Naive Att {i+1}: verdict={h.get('verdict')}, reason={h.get('reason')}")
        if "failures" in h:
            for f in h["failures"]:
                tb = f.get("traceback", "")
                for line in tb.splitlines():
                    if "E   " in line or "AssertionError" in line:
                        print(f"    Naive failure: {line.strip()}")
