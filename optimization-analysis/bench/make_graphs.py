#!/usr/bin/env python3
"""Graphs for the article, drawn only from measured trials. Usage: python3 make_graphs.py data/trials_full_XXXX.jsonl"""
import sys, os, json, statistics as st, random, collections
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import analyze as A

trials_path = sys.argv[1]
watcher = trials_path.replace("trials_", "watcher_")
pods, jobs, events = A.load_watcher(watcher)
rows = [json.loads(l) for l in open(trials_path)]

S = collections.defaultdict(lambda: collections.defaultdict(list)); pulled_flag = collections.defaultdict(list)
for tr in rows:
    if tr["warmup"]: continue
    s = A.stages(tr, pods, jobs, events)
    if s is None: continue
    if (not tr.get("cold")) and s.get("_pulled") is True:   # cached-config trial that actually pulled (landed on a fresh node)
        pulled_flag[tr["config"]].append(s); continue
    for k, v in s.items():
        if v is not None and not k.startswith("_pull") or k == "_pull_ms" and v is not None:
            S[tr["config"]][k].append(v)

INK, INK2, GRID, BG = "#0b0b0b", "#52514e", "#e6e5e1", "#fcfcfb"
C_POLL, C_SCHED, C_PULL, C_START, C_NEUTRAL = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#8a8985"
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.facecolor": BG, "figure.facecolor": BG, "axes.edgecolor": GRID,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2, "text.color": INK})


def frame(ax, xgrid=True):
    for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    if xgrid: ax.xaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True); ax.tick_params(length=0)


def titles(fig, title, sub, note=None):
    fig.text(0.02, 0.965, title, fontsize=15, fontweight="bold", va="top", ha="left")
    fig.text(0.02, 0.905, sub, fontsize=10.5, color=INK2, va="top", ha="left")
    if note: fig.text(0.02, 0.015, note, fontsize=8.5, color=INK2, va="bottom", ha="left")


def n_of(cfg): return len(S[cfg]["total"])


# ---------- Graph A: where the time goes (mean stack) ----------
def graph_stack():
    order = [("warm_blpop", "Warm pool, blocking pop"), ("warm_poll1s", "Warm pool, 1s poll loop"),
             ("poll1", "ScaledJob, 1s polling (image cached)"), ("alpine_warm", "ScaledJob, 1s polling, Alpine (cached)"),
             ("slim_cold", "ScaledJob, 1s polling, cold pull: slim"), ("alpine_cold", "ScaledJob, 1s polling, cold pull: Alpine"),
             ("distroless_cold", "ScaledJob, 1s polling, cold pull: distroless")]
    fig, ax = plt.subplots(figsize=(11, 5.4)); fig.subplots_adjust(left=0.33, right=0.96, top=0.80, bottom=0.14)
    for i, (cfg, label) in enumerate(order):
        y = len(order) - 1 - i; d = S[cfg]
        if cfg.startswith("warm_"):
            segs = [("Queue wait / polling", st.mean(d["total"]), C_POLL)]
        else:
            pull = st.mean(d["_pull_ms"]) if d.get("_pull_ms") and len(d["_pull_ms"]) > 3 else 0
            segs = [("Queue wait / polling", st.mean(d["detect"]), C_POLL),
                    ("Scheduling", st.mean(d["job_to_pod"]) + st.mean(d["sched"]), C_SCHED),
                    ("Image pull", pull, C_PULL),
                    ("Container start", st.mean(d["post_sched"]) - pull, C_START)]
        x = 0
        for name, w, c in segs:
            if w <= 0: continue
            ax.barh(y, w, left=x, height=0.56, color=c, edgecolor=BG, linewidth=2)
            if w > 260: ax.text(x + w / 2, y, "%.0f" % w, ha="center", va="center", fontsize=9, color=INK, fontweight="bold")
            x += w
        ax.text(x + 40, y, "%.0f ms" % x if x >= 10 else "%.0f ms" % x, va="center", fontsize=10, fontweight="bold")
        ax.text(x + 40, y - 0.36, "n=%d" % n_of(cfg), va="center", fontsize=7.5, color=INK2)
    ax.set_yticks(range(len(order))); ax.set_yticklabels([l for _, l in order][::-1], fontsize=10)
    ax.set_xlim(0, 3300); ax.set_xlabel("Mean milliseconds from message sent to handler running")
    frame(ax)
    for name, c, dx in [("Queue wait / polling", C_POLL, 0), ("Scheduling", C_SCHED, 0.19), ("Image pull", C_PULL, 0.33), ("Container start", C_START, 0.45)]:
        fig.patches.append(plt.Rectangle((0.33 + dx, 0.835), 0.012, 0.02, transform=fig.transFigure, color=c))
        fig.text(0.348 + dx, 0.845, name, fontsize=9.5, va="center", color=INK2)
    titles(fig, "Where a cold start's time goes", "Mean of up to 20 trials per condition (n shown per bar). Scheduling (job + pod placement) is ~15 ms and too thin to see.",
           "Container start includes Python interpreter boot (handler time is taken at its first line). Queue is Redis: no SQS network latency.")
    fig.savefig("graphs/graph_4_time_breakdown.png", dpi=200); plt.close(fig)


# ---------- Graph B: polling interval vs detection wait ----------
def graph_polling():
    cfgs = [("poll1", 1), ("poll5", 5), ("poll10", 10), ("poll30", 30)]
    fig, ax = plt.subplots(figsize=(9, 5.6)); fig.subplots_adjust(left=0.10, right=0.95, top=0.80, bottom=0.14)
    rnd = random.Random(2)
    for i, (cfg, T) in enumerate(cfgs):
        v = [x / 1000 for x in S[cfg]["detect"]]
        ax.scatter([i + rnd.uniform(-0.16, 0.16) for _ in v], v, s=34, color=C_POLL, alpha=0.75, edgecolor=BG, linewidth=0.8, zorder=3)
        m = st.median(v); ax.hlines(m, i - 0.30, i + 0.30, color=INK, lw=2.4, zorder=4)
        ax.text(i + 0.33, m, "median %.1fs" % m, va="center", fontsize=9, fontweight="bold")
        ax.hlines(T, i - 0.30, i + 0.30, color=INK2, lw=1.2, ls=(0, (4, 3)), zorder=2)
        ax.text(i - 0.33, T, "interval %ds" % T, va="bottom", ha="right", fontsize=8.5, color=INK2)
    ax.set_xticks(range(4)); ax.set_xticklabels(["1s", "5s", "10s", "30s"], fontsize=11)
    ax.set_xlabel("KEDA pollingInterval"); ax.set_ylabel("Seconds until KEDA created the Job"); ax.set_xlim(-0.6, 3.75); ax.set_ylim(0, 32)
    frame(ax, xgrid=False); ax.yaxis.grid(True, color=GRID, lw=0.8)
    titles(fig, "Polling interval sets the detection wait", "Each dot is one trial (19-20 per interval). Waits spread from 0 to the interval; the median is about half.",
           "Message send time was randomised relative to KEDA's poll loop.")
    fig.savefig("graphs/graph_2_polling_wait.png", dpi=200); plt.close(fig)


# ---------- Graph C: cached vs cold pull ----------
def graph_pull():
    order = [("poll1", "Cached: python:3.12-slim (43.5 MB)", C_NEUTRAL), ("alpine_warm", "Cached: python:3.12-alpine (18.5 MB)", C_NEUTRAL),
             ("slim_cold", "Cold pull: python:3.12-slim (43.5 MB)", C_PULL), ("alpine_cold", "Cold pull: python:3.12-alpine (18.5 MB)", C_PULL),
             ("distroless_cold", "Cold pull: distroless/python3 (22.6 MB)", C_PULL)]
    fig, ax = plt.subplots(figsize=(10.5, 5.2)); fig.subplots_adjust(left=0.36, right=0.94, top=0.80, bottom=0.15)
    rnd = random.Random(5)
    for i, (cfg, label, c) in enumerate(order):
        y = len(order) - 1 - i; v = S[cfg]["podstart"]
        ax.scatter(v, [y + rnd.uniform(-0.17, 0.17) for _ in v], s=30, color=c, alpha=0.8, edgecolor=BG, linewidth=0.8, zorder=3)
        m = st.median(v); ax.vlines(m, y - 0.32, y + 0.32, color=INK, lw=2.4, zorder=4)
        ax.text(max(v) + 60, y, "median %.0f ms" % m, va="center", fontsize=9.5, fontweight="bold")
    ax.set_yticks(range(len(order))); ax.set_yticklabels([o[1] for o in order][::-1], fontsize=10)
    ax.set_xlim(0, 3600); ax.set_xlabel("Milliseconds from pod created to handler running"); frame(ax)
    titles(fig, "A cold image pull adds ~1.2 s; smaller images did not shorten it",
           "Each dot is one trial (19-20 per row); black tick = median. Sizes are compressed registry sizes reported by containerd.",
           "Distroless is served from gcr.io, the others from Docker Hub, so its slower pulls may reflect the registry rather than the image.")
    fig.savefig("graphs/graph_3_cold_pull.png", dpi=200); plt.close(fig)


# ---------- Graph D: scheduling is not the bottleneck (stage durations, log axis) ----------
def graph_stages():
    cached = [c for c in ("poll1", "poll5", "poll10", "poll30", "alpine_warm")]
    jp = sum((S[c]["job_to_pod"] for c in cached), []); sc = sum((S[c]["sched"] for c in cached), [])
    ps = sum((S[c]["post_sched"] for c in cached), [])
    pull = sum((S[c]["_pull_ms"] for c in ("slim_cold", "alpine_cold", "distroless_cold")), [])
    data = [("Job created → pod created", jp, C_SCHED), ("Pod created → scheduled to a node", sc, C_SCHED),
            ("Scheduled → handler running\n(image already cached)", ps, C_START), ("Cold image pull", pull, C_PULL)]
    fig, ax = plt.subplots(figsize=(10.5, 4.9)); fig.subplots_adjust(left=0.30, right=0.94, top=0.79, bottom=0.17)
    rnd = random.Random(9)
    for i, (label, v, c) in enumerate(data):
        y = len(data) - 1 - i; v = [x for x in v if x > 0]  # drop watch-event ordering artifacts (<=0 ms)
        ax.scatter(v, [y + rnd.uniform(-0.2, 0.2) for _ in v], s=14, color=c, alpha=0.6, edgecolor="none", zorder=3)
        m = st.median(v); ax.vlines(m, y - 0.33, y + 0.33, color=INK, lw=2.4, zorder=4)
        ax.text(max(v) * 1.25, y, "median %.0f ms  (n=%d)" % (m, len(v)), va="center", fontsize=9.5, fontweight="bold")
    ax.set_xscale("log"); ax.set_xlim(1, 30000); ax.set_xticks([1, 10, 100, 1000, 10000]); ax.set_xticklabels(["1", "10", "100", "1,000", "10,000"])
    ax.set_yticks(range(len(data))); ax.set_yticklabels([d[0] for d in data][::-1], fontsize=10)
    ax.set_xlabel("Milliseconds (log scale)"); frame(ax)
    titles(fig, "Scheduling took ~17 ms here; container start and image pulls dominate",
           "Every measured trial, by stage, on a 3-node k3d cluster with an idle scheduler.",
           "Job → pod and pod → scheduled: all ScaledJob trials with the image already cached. Handler-running time includes Python boot.")
    fig.savefig("graphs/graph_1_stage_durations.png", dpi=200); plt.close(fig)


for f in (graph_stack, graph_polling, graph_pull, graph_stages): f()
print({k: len(v["total"]) for k, v in S.items()}, {k: len(v) for k, v in pulled_flag.items()})
