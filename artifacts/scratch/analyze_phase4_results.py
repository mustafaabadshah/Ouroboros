import json
import math
from pathlib import Path

artifact_path = Path("artifacts/v0_11/mock_agent_ablation_15tasks.json")
data = json.loads(artifact_path.read_text(encoding="utf-8"))

trials_on = data["raw_trials"]["memory_enabled_trials"][0]
trials_off = data["raw_trials"]["baseline_trials"][0]

tasks_on = {t["task_id"]: t for t in trials_on["task_results"]}
tasks_off = {t["task_id"]: t for t in trials_off["task_results"]}

print("=" * 80)
print("PAIRED TASK-LEVEL ABLATION MATRIX (15 POSITIVE TASKS)")
print("=" * 80)
print(f"{'Task ID':<10} | {'Category':<24} | {'Flywheel':<9} | {'Naive':<9} | {'Att (FW/NV)':<12} | {'Dur FW (ms)':<12} | {'Dur NV (ms)':<12}")
print("-" * 100)

categories = {}

for tid in tasks_on:
    t_on = tasks_on[tid]
    t_off = tasks_off[tid]
    cat = t_on["category"]
    
    if cat not in categories:
        categories[cat] = {"tasks": [], "fw_pass": 0, "nv_pass": 0, "fw_dur": [], "nv_dur": []}
    
    categories[cat]["tasks"].append(tid)
    if t_on["verdict"] == "PASS":
        categories[cat]["fw_pass"] += 1
    if t_off["verdict"] == "PASS":
        categories[cat]["nv_pass"] += 1
    categories[cat]["fw_dur"].append(t_on["duration_ms"])
    categories[cat]["nv_dur"].append(t_off["duration_ms"])

    att_str = f"{t_on['attempts_executed']} / {t_off['attempts_executed']}"
    print(f"{tid:<10} | {cat:<24} | {t_on['verdict']:<9} | {t_off['verdict']:<9} | {att_str:<12} | {t_on['duration_ms']:<12} | {t_off['duration_ms']:<12}")

print("=" * 80)
print("CATEGORY-LEVEL SUMMARY")
print("=" * 80)
for cat, info in categories.items():
    fw_rate = (info["fw_pass"] / len(info["tasks"])) * 100
    nv_rate = (info["nv_pass"] / len(info["tasks"])) * 100
    avg_fw_dur = sum(info["fw_dur"]) / len(info["fw_dur"])
    avg_nv_dur = sum(info["nv_dur"]) / len(info["nv_dur"])
    print(f"Category: {cat:<24} | Tasks: {len(info['tasks'])} | Flywheel: {info['fw_pass']}/{len(info['tasks'])} ({fw_rate:.1f}%) | Naive: {info['nv_pass']}/{len(info['tasks'])} ({nv_rate:.1f}%) | Avg Dur: FW={avg_fw_dur:.0f}ms, NV={avg_nv_dur:.0f}ms")

print("=" * 80)
print("AGGREGATE SUMMARY & STATISTICAL METRICS")
print("=" * 80)
summary = data["statistical_summary"]
sum_on = summary["memory_enabled"]
sum_off = summary["naive_retry_baseline"]
paired = summary["paired_comparison"]

print(f"Flywheel Pooled Pass Rate: {sum_on['pooled_pass_rate']*100:.2f}% (Wilson 95% CI: [{sum_on['wilson_ci_95']['lower']}, {sum_on['wilson_ci_95']['upper']}])")
print(f"Naive Retry Pass Rate:     {sum_off['pooled_pass_rate']*100:.2f}% (Wilson 95% CI: [{sum_off['wilson_ci_95']['lower']}, {sum_off['wilson_ci_95']['upper']}])")
print(f"Pass Rate Delta (Delta):   {paired['eligible_repair_pass_rate_delta']*100:+.2f} percentage points")
print(f"Flywheel Median Duration:  {trials_on['median_duration_ms']} ms")
print(f"Naive Retry Median Dur:    {trials_off['median_duration_ms']} ms")
print(f"Total Tokens FW:           In: {trials_on.get('total_tokens_in')} | Out: {trials_on.get('total_tokens_out')}")
print(f"Total Tokens NV:           In: {trials_off.get('total_tokens_in')} | Out: {trials_off.get('total_tokens_out')}")

# Discordant pairs and McNemar calculation
b = sum(1 for tid in tasks_on if tasks_on[tid]["verdict"] == "PASS" and tasks_off[tid]["verdict"] != "PASS")
c = sum(1 for tid in tasks_on if tasks_on[tid]["verdict"] != "PASS" and tasks_off[tid]["verdict"] == "PASS")
a = sum(1 for tid in tasks_on if tasks_on[tid]["verdict"] == "PASS" and tasks_off[tid]["verdict"] == "PASS")
d = sum(1 for tid in tasks_on if tasks_on[tid]["verdict"] != "PASS" and tasks_off[tid]["verdict"] != "PASS")

print(f"\nContingency Matrix: a(Both PASS)={a}, b(FW only)={b}, c(NV only)={c}, d(Both FAIL)={d}")
n_discordant = b + c
if n_discordant > 0:
    # Exact two-tailed binomial test under H0: p=0.5
    p_val = 2 * (0.5 ** n_discordant) * sum(math.comb(n_discordant, k) for k in range(max(b, c), n_discordant + 1))
    p_val = min(1.0, p_val)
    print(f"Exact McNemar Test (Two-Tailed): p = {p_val:.6f} ({'p < 0.001' if p_val < 0.001 else 'p >= 0.001'})")

print("\n" + "=" * 80)
print("DEEP FORENSIC INSPECTION: BENCH-04 FAILURE IN CONDITION 1")
print("=" * 80)
b4_on = tasks_on["BENCH-04"]
print(f"Outcome: {b4_on['outcome']}, Verdict: {b4_on['verdict']}, Attempts: {b4_on['attempts_executed']}")
for h in b4_on.get("history", []):
    print(f"  Attempt {h.get('attempt')}: verdict={h.get('verdict')}, acceptance_passed={h.get('acceptance_passed')}, regression_passed={h.get('regression_passed')}, reason={h.get('reason')}")
    if "candidate_patch" in h:
        print(f"    Patch excerpt: {h['candidate_patch'][:150]}...")
