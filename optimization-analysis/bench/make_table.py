#!/usr/bin/env python3
import sys, json, statistics as st, collections
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import analyze as A
t = sys.argv[1]
pods, jobs, ev = A.load_watcher(t.replace("trials_", "watcher_"))
S = collections.defaultdict(lambda: collections.defaultdict(list))
for tr in (json.loads(l) for l in open(t)):
    if tr["warmup"]: continue
    s = A.stages(tr, pods, jobs, ev)
    if not s: continue
    if (not tr.get("cold")) and s.get("_pulled") is True: continue
    for k, v in s.items():
        if v is not None: S[tr["config"]][k].append(v)
rows_spec = [("poll30", "ScaledJob, 30s polling (default)", "Polling wait"), ("poll10", "ScaledJob, 10s polling", "Polling wait"),
             ("poll5", "ScaledJob, 5s polling", "Polling wait"), ("poll1", "ScaledJob, 1s polling", "Polling + container start"),
             ("alpine_warm", "ScaledJob, 1s polling, Alpine", "Polling + container start"),
             ("slim_cold", "ScaledJob, 1s, cold pull (slim)", "Image pull"), ("alpine_cold", "ScaledJob, 1s, cold pull (Alpine)", "Image pull"),
             ("distroless_cold", "ScaledJob, 1s, cold pull (distroless)", "Image pull"),
             ("warm_poll1s", "Warm pool, 1s poll loop", "Poll loop"), ("warm_blpop", "Warm pool, blocking pop", "Nothing measurable")]
def p95(x): return A.pct(x, 95)
def fmt(ms): return "%.0f ms" % ms if ms < 1000 else "%.1f s" % (ms / 1000)
out = []
for cfg, label, dom in rows_spec:
    x = S[cfg]["total"]; out.append((label, str(len(x)), fmt(st.median(x)), fmt(p95(x)), dom))
    print(cfg, len(x), "median %.0f p95 %.0f mean %.0f" % (st.median(x), p95(x), st.mean(x)))
hdr = ("Setup", "Trials", "Median", "p95", "Biggest cost")
W = [0.40, 0.08, 0.12, 0.12, 0.28]
fig, ax = plt.subplots(figsize=(10.5, 0.52 * (len(out) + 1) + 1.35)); ax.axis("off")
fig.patch.set_facecolor("#fcfcfb")
fig.text(0.02, 0.965, "Message sent to handler running, by setup", fontsize=14, fontweight="bold", va="top")
fig.text(0.02, 0.905, "Measured on a 3-node k3d cluster, Redis queue, up to 20 trials per row (cached rows exclude trials that landed on a node without the image).", fontsize=9, color="#52514e", va="top")
top = 0.80; rh = 0.68 / (len(out) + 1)
def cell(x0, y, w, text, bold=False, align="left", color="#0b0b0b"):
    xx = x0 + (0.008 if align == "left" else w - 0.012)
    fig.text(xx, y, text, fontsize=10, fontweight="bold" if bold else "normal", va="center", ha=align, color=color)
x0 = 0.02; y = top - rh / 2
for i, h in enumerate(hdr):
    cell(x0 + sum(W[:i]) * 0.96, y, W[i] * 0.96, h, bold=True, align="left" if i in (0, 4) else "right", color="#52514e")
fig.add_artist(plt.Line2D([0.02, 0.98], [top - rh, top - rh], color="#0b0b0b", lw=1.2))
for r, row in enumerate(out):
    y = top - rh * (r + 1.5)
    if r % 2 == 0: fig.add_artist(plt.Rectangle((0.02, y - rh / 2), 0.96, rh, color="#f3f2ee", transform=fig.transFigure, zorder=0))
    for i, v in enumerate(row):
        cell(x0 + sum(W[:i]) * 0.96, y, W[i] * 0.96, v, bold=(i == 2), align="left" if i in (0, 4) else "right")
fig.savefig("graphs/graph_5_results_table.png", dpi=200); print("saved")
