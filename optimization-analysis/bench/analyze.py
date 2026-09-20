#!/usr/bin/env python3
"""Turn trials_*.jsonl + watcher_*.jsonl into stage timings, stats and CIs (stdlib only).
Usage: python3 analyze.py data/trials_full_XXXX.jsonl [--watcher data/watcher_full_XXXX.jsonl]"""
import argparse, collections, csv, json, math, os, random, re, statistics as st, sys

STAGES = ["detect", "job_to_pod", "sched", "post_sched", "podstart", "total"]


def pct(xs, p):
    xs = sorted(xs)
    if not xs: return float("nan")
    k = (len(xs) - 1) * p / 100.0
    lo, hi = int(math.floor(k)), int(math.ceil(k))
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def parse_dur(msg):
    m = re.search(r"in (?:(\d+)m)?([\d.]+)(ms|s)\b", msg or "")
    if not m: return None
    v = float(m.group(2)) * (1 if m.group(3) == "ms" else 1000)
    return v + (int(m.group(1)) * 60000 if m.group(1) else 0)


def load_watcher(path):
    pods = collections.defaultdict(list); jobs = {}; events = collections.defaultdict(list)
    for line in open(path):
        try: r = json.loads(line)
        except Exception: continue
        if r.get("kind") == "Pod" and r["type"] in ("ADDED", "MODIFIED"): pods[r["name"]].append(r)
        elif r.get("kind") == "Job" and r["type"] == "ADDED": jobs[r["name"]] = min(jobs.get(r["name"], 1e18), r["t"])
        elif r.get("kind") == "Event" and r.get("ikind") == "Pod": events[r["pod"]].append(r)
    return pods, jobs, events


def stages(tr, pods, jobs, events):
    res = tr["result"]
    if not res: return None
    ts, th = tr["t_send"], res["t_start"]
    out = {"total": (th - ts) * 1000}
    pod = res.get("pod")
    if tr["config"].startswith("warm_") or pod not in pods: return out
    recs = pods[pod]
    t_pod = min(r["t"] for r in recs if r["type"] == "ADDED")
    t_sched = min([r["t"] for r in recs if r.get("node")] or [None], key=lambda x: (x is None, x))
    job = next((r["job"] for r in recs if r.get("job")), None)
    t_job = jobs.get(job)
    if t_job: out["detect"] = (t_job - ts) * 1000; out["job_to_pod"] = (t_pod - t_job) * 1000
    if t_sched: out["sched"] = (t_sched - t_pod) * 1000
    if t_sched: out["post_sched"] = (th - t_sched) * 1000   # pull + create + start + interpreter boot
    out["podstart"] = (th - t_pod) * 1000
    pulled = None; pull_ms = None
    for e in events.get(pod, []):
        if e.get("reason") == "Pulled":
            if "already present" in (e.get("message") or ""): pulled = False
            else: pulled = True; pull_ms = parse_dur(e.get("message"))
    out["_pulled"] = pulled; out["_pull_ms"] = pull_ms
    return out


def boot_diff(a, b, stat=st.median, B=5000, seed=1):
    rnd = random.Random(seed); d = []
    for _ in range(B):
        d.append(stat([rnd.choice(b) for _ in b]) - stat([rnd.choice(a) for _ in a]))
    d.sort()
    return stat(b) - stat(a), d[int(0.025 * B)], d[int(0.975 * B)]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("trials"); ap.add_argument("--watcher")
    a = ap.parse_args()
    watcher = a.watcher or a.trials.replace("trials_", "watcher_")
    pods, jobs, events = load_watcher(watcher) if os.path.exists(watcher) else ({}, {}, {})
    rows = [json.loads(l) for l in open(a.trials)]
    by = collections.defaultdict(lambda: collections.defaultdict(list)); flags = collections.Counter()
    table = []
    for tr in rows:
        if tr["warmup"]: continue
        s = stages(tr, pods, jobs, events)
        if s is None: flags[(tr["config"], "no_result")] += 1; continue
        if tr.get("cold") and s.get("_pulled") is False: flags[(tr["config"], "cold_but_cached")] += 1; continue
        if tr.get("cold") and s.get("_pulled") is None and pods: flags[(tr["config"], "pull_unverified")] += 1
        if (not tr.get("cold")) and s.get("_pulled") is True: flags[(tr["config"], "warm_but_pulled")] += 1
        for k in STAGES + ["_pull_ms"]:
            if s.get(k) is not None: by[tr["config"]][k].append(s[k])
        table.append(dict(config=tr["config"], trial=tr["trial"], **{k: (round(s[k], 1) if s.get(k) is not None else "") for k in STAGES + ["_pull_ms"]}))
    L = ["# Measured cold-start decomposition (ms)", "",
         "Timestamps: single clock inside the cluster (ms resolution). `total` = message sent -> handler running.", ""]
    hdr = "| config | n | metric | mean | median | p95 | min | max |\n|---|---|---|---|---|---|---|---|"
    L.append(hdr)
    summ = {}
    for cfg in sorted(by):
        for k in STAGES + ["_pull_ms"]:
            x = by[cfg].get(k)
            if not x: continue
            summ.setdefault(cfg, {})[k] = dict(n=len(x), mean=st.mean(x), median=st.median(x), p95=pct(x, 95), min=min(x), max=max(x),
                                                sd=st.stdev(x) if len(x) > 1 else 0)
            m = summ[cfg][k]
            L.append("| %s | %d | %s | %.0f | %.0f | %.0f | %.0f | %.0f |" % (cfg, m["n"], k, m["mean"], m["median"], m["p95"], m["min"], m["max"]))
    L += ["", "## Comparisons (difference of medians, 95% bootstrap CI; B minus A)", "",
          "| A | B | metric | diff (ms) | 95% CI |", "|---|---|---|---|---|"]
    cmp = [("poll1", "slim_cold", "podstart"), ("poll1", "alpine_warm", "podstart"), ("slim_cold", "alpine_cold", "podstart"),
           ("slim_cold", "distroless_cold", "podstart"), ("slim_cold", "alpine_cold", "_pull_ms"), ("poll30", "poll1", "detect"), ("poll10", "poll1", "detect"),
           ("poll5", "poll1", "detect"), ("poll1", "warm_blpop", "total"), ("poll1", "warm_poll1s", "total"), ("poll1", "slim_cold", "total")]
    comps = []
    for A, B, k in cmp:
        if by[A].get(k) and by[B].get(k) and len(by[A][k]) > 2 and len(by[B][k]) > 2:
            d, lo, hi = boot_diff(by[A][k], by[B][k]); comps.append(dict(A=A, B=B, metric=k, diff=d, lo=lo, hi=hi))
            L.append("| %s | %s | %s | %+.0f | (%+.0f, %+.0f) |" % (A, B, k, d, lo, hi))
    if flags:
        L += ["", "## Data-quality flags", ""] + ["- %s: %s x%d" % (c, f, n) for (c, f), n in sorted(flags.items())]
    out = os.path.splitext(a.trials)[0]
    open(out.replace("trials_", "summary_") + ".md", "w").write("\n".join(L) + "\n")
    json.dump(dict(summary=summ, comparisons=comps, flags={"%s:%s" % k: v for k, v in flags.items()}), open(out.replace("trials_", "summary_") + ".json", "w"), indent=1)
    with open(out.replace("trials_", "rows_") + ".csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["config", "trial"] + STAGES + ["_pull_ms"]); w.writeheader(); w.writerows(table)
    print("\n".join(L))


if __name__ == "__main__":
    main()
