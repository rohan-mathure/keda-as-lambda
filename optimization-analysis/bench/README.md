# Cold-start decomposition benchmark

Measures where the time goes between "message sent" and "handler running" for KEDA ScaledJobs and for a warm worker pool, using millisecond timestamps taken inside the cluster.

## What it measures
Per trial: message sent, Job created, Pod created, Pod scheduled, handler first line. A watcher pod records every Job/Pod/Event change on the same clock as the handlers. Trials send one message at a time with the send time randomised against KEDA's poll loop; conditions run in random order.

Conditions (20 trials each): ScaledJob polling 30s/10s/5s/1s (image cached), Alpine cached, cold pull of slim/Alpine/distroless (image deleted from every node first, pull confirmed from the kubelet `Pulled` event), warm pool with a 1s poll loop, warm pool with a blocking pop.

The queue is a Redis list (KEDA redis scaler), so no SQS network latency is included.

## Run it
Needs a k3d cluster with KEDA installed, `kubectl`, `docker`, `python3` (stdlib only; matplotlib for graphs).

    bash preflight.sh                       # read-only checks -> data/preflight.txt
    bash setup.sh                           # creates namespace `bench`: redis, pusher, watcher
    python3 run_trials.py --quick           # smoke test, 3 trials per condition
    caffeinate -i python3 run_trials.py --n 20 --distroless
    python3 analyze.py data/trials_full_<tag>.jsonl
    python3 make_graphs.py data/trials_full_<tag>.jsonl
    python3 make_table.py  data/trials_full_<tag>.jsonl

Pause other ScaledJobs first (they add noise), and clean up afterwards with `kubectl delete ns bench`.

## Files
- `data/trials_full_20260920T033600.jsonl`: one row per trial (raw)
- `data/watcher_full_20260920T033600.jsonl`: raw Job/Pod/Event timeline
- `data/summary_full_*.md|json`, `data/rows_full_*.csv`: analysis output
- `graphs/`: figures used in the article

## Caveats
3-node k3d on a laptop, idle scheduler, images pulled over a home connection, Redis instead of SQS. Numbers show the mechanism, not what your production cluster will do.
