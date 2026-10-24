"""Print the Markdown tables used in 04/05 from benchmarks/results/*.json.

    apps/backend/.venv/bin/python benchmarks/report_tables.py > benchmarks/results/tables.md

Medians across repetitions; ranges show min-max across repetitions.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

RES = Path(__file__).resolve().parent / "results"


def load(name):
    p = RES / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


def rng(vals, fmt="{:.1f}"):
    return f"{fmt.format(statistics.median(vals))} ({fmt.format(min(vals))}–{fmt.format(max(vals))})"


def api(tag):
    d = load(f"api_latency_{tag}")
    if not d:
        return
    print(f"\n### B1 read endpoints — {tag}\n")
    print("| Endpoint | Conc. | p50 ms | p95 ms | p99 ms | req/s | server CPU (cores) |")
    print("|---|---|---|---|---|---|---|")
    keys = list(dict.fromkeys((c["endpoint"], c["concurrency"]) for c in d["cells"]))
    for ep, cc in keys:
        cells = [c for c in d["cells"] if c["endpoint"] == ep and c["concurrency"] == cc]
        non200 = sum(v for c in cells for k, v in c["statuses"].items() if k != "200")
        print(f"| `{ep}` | {cc} | {rng([c['p50_ms'] for c in cells], '{:.2f}')} | "
              f"{rng([c['p95_ms'] for c in cells], '{:.2f}')} | {rng([c['p99_ms'] for c in cells], '{:.2f}')} | "
              f"{rng([c['throughput_rps'] for c in cells], '{:.0f}')} | "
              f"{rng([c['server_cpu_util'] for c in cells], '{:.2f}')}"
              f"{' (non-200: ' + str(non200) + ')' if non200 else ''} |")


def generate(tag):
    d = load(f"generate_{tag}")
    if not d:
        return
    print(f"\n### B2 generate overhead — {tag} (simulated provider, 0 s)\n")
    print("| Photo | Upload MB | p50 ms | p95 ms | server CPU ms/req |")
    print("|---|---|---|---|---|")
    for photo in dict.fromkeys(c["photo"] for c in d["overhead"]):
        cells = [c for c in d["overhead"] if c["photo"] == photo]
        print(f"| {photo} | {cells[0]['bytes']/1e6:.2f} | {rng([c['p50_ms'] for c in cells])} | "
              f"{rng([c['p95_ms'] for c in cells])} | {rng([c['server_cpu_ms_per_req'] for c in cells])} |")
    print("\n| Burst (MAX_CONCURRENT=2, model 2 s) | Statuses | Provider calls | Served p50 ms | Slowest 503 ms |")
    print("|---|---|---|---|---|")
    for c in d["shedding"]:
        print(f"| {c['burst']} | {c['statuses']} | {c['provider_calls']} | {c['served_p50_ms']} | {c['shed_max_ms']} |")
    print("\n| In flight (7.6 MB uploads, model 1 s) | Idle RSS MB | Peak RSS MB | Growth MB |")
    print("|---|---|---|---|")
    for c in d["memory"]:
        print(f"| {c['concurrency']} | {c['rss_idle_mb']} | {c['rss_peak_mb']} | {c['rss_growth_mb']} |")


def reliability(tag):
    d = load(f"reliability_{tag}")
    if not d:
        return
    print(f"\n### B3 reliability — {tag} (simulated provider, timeout 2 s)\n")
    print("| Provider behaviour | HTTP | mode | fallbackReason | wall s |")
    print("|---|---|---|---|---|")
    for r in d["provider_failures"]:
        print(f"| {r['case']} | {r['status']} | {r.get('mode')} | {r.get('fallbackReason')} | {r['wall_s']} |")
    print("\n| Duplicate case | Provider calls | Same resultId |")
    print("|---|---|---|")
    for r in d["duplicates"]:
        print(f"| {r['case']} | {r['provider_calls']} | {r['same_result']} |")
    print("\n| Budget race (limit 50, 300 requests, 16 clients) | Provider calls per trial | HTTP 500s per trial |")
    print("|---|---|---|")
    for w in (1, 4):
        rows = [r for r in d["budget_race"] if r["workers"] == w]
        calls = [r["provider_calls"] for r in rows]
        errs = [sum(v for k, v in r["statuses"].items() if k.startswith("500")) for r in rows]
        print(f"| {w} worker(s) | {calls} | {errs} |")
    print("\n| Damaged upload | HTTP | reached provider |")
    print("|---|---|---|")
    for r in d["corrupt_uploads"]:
        print(f"| {r['case']} | {r['status']} | {r['reached_provider']} |")
    print(f"\nRate limit, 6 forged X-Forwarded-For: {d['rate_limits']['statuses']}  ")
    db = d["daily_budget"]
    print(f"Daily budget 5, 8 requests: {db['statuses']}, provider calls {db['provider_calls']}  ")
    print(f"Body limits: {d['body_limits']}  ")
    print(f"Restart: {d['restart_recovery']}")


def stages(tag):
    d = load(f"stages_{tag}")
    if not d:
        return
    print(f"\n### B2b stage timing — {tag}\n")
    print("| Photo | Stage | median ms | p95 ms |")
    print("|---|---|---|---|")
    for r in d["rows"]:
        print(f"| {r['photo'] or '-'} | {r['stage']} | {r['median_ms']} | {r['p95_ms']} |")


if __name__ == "__main__":
    for tag in ("baseline", "after"):
        api(tag)
        generate(tag)
        reliability(tag)
        stages(tag)
