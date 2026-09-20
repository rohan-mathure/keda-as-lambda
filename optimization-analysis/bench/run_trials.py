#!/usr/bin/env python3
"""Cold-start decomposition harness for KEDA ScaledJob vs warm pool (stdlib only).
Run on the Mac (needs kubectl + docker). Usage:
  python3 run_trials.py --quick            # 3 trials per condition (smoke test)
  python3 run_trials.py                    # full run, N=20 per condition
  python3 run_trials.py --only poll1 slim_cold --n 10
"""
import argparse, json, os, random, re, subprocess, sys, time, datetime

NS = "bench"
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
HANDLER = open(os.path.join(HERE, "job_handler.py")).read()
PUSH = open(os.path.join(HERE, "push.py")).read()
POP = open(os.path.join(HERE, "pop_result.py")).read()

IMAGES = {"slim": "python:3.12-slim", "alpine": "python:3.12-alpine",
          "distroless": "gcr.io/distroless/python3"}
CANON = {"slim": "docker.io/library/python:3.12-slim",
         "alpine": "docker.io/library/python:3.12-alpine",
         "distroless": "gcr.io/distroless/python3"}
CMD = {"slim": ["python", "-c"], "alpine": ["python", "-c"],
       "distroless": ["/usr/bin/python3", "-c"]}

CONFIGS = [
    dict(name="poll30", kind="job", poll=30, image="slim", cold=False),
    dict(name="poll10", kind="job", poll=10, image="slim", cold=False),
    dict(name="poll5", kind="job", poll=5, image="slim", cold=False),
    dict(name="poll1", kind="job", poll=1, image="slim", cold=False),
    dict(name="alpine_warm", kind="job", poll=1, image="alpine", cold=False),
    dict(name="slim_cold", kind="job", poll=1, image="slim", cold=True),
    dict(name="alpine_cold", kind="job", poll=1, image="alpine", cold=True),
    dict(name="distroless_cold", kind="job", poll=1, image="distroless", cold=True, optional=True),
    dict(name="warm_blpop", kind="pool", mode="blpop"),
    dict(name="warm_poll1s", kind="pool", mode="poll1s"),
]


def kc(*args, input=None, check=True, timeout=180):
    r = subprocess.run(["kubectl", *args], input=input, capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError("kubectl %s failed: %s" % (" ".join(args[:4]), r.stderr.strip()))
    return r.stdout


def push(tid):
    out = kc("-n", NS, "exec", "deploy/pusher", "--", "python", "-c", PUSH, tid)
    return json.loads(out.strip().splitlines()[-1])


def pop_result(tid, timeout):
    deadline = time.time() + timeout
    while time.time() < deadline:
        out = kc("-n", NS, "exec", "deploy/pusher", "--", "python", "-c", POP,
                 str(max(1, int(deadline - time.time()))), timeout=timeout + 60).strip()
        if out == "TIMEOUT":
            return None
        r = json.loads(out)
        if r.get("id") == tid or r.get("nil"):
            if r.get("nil"):
                continue  # duplicate job that found empty queue; keep waiting
            return r
    return None


def nodes():
    names = subprocess.run(["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True).stdout.split()
    return [n for n in names if re.match(r"k3d-.*-(server|agent)-\d+$", n)]


def evict(image_key):
    for n in nodes():
        for cri in (["crictl"], ["k3s", "crictl"]):
            r = subprocess.run(["docker", "exec", n, *cri, "rmi", CANON[image_key]], capture_output=True, text=True)
            if r.returncode == 0 or "not found" in (r.stderr + r.stdout).lower() or "no such image" in (r.stderr + r.stdout).lower():
                break


def scaledjob(cfg):
    img = IMAGES[cfg["image"]]
    return {"apiVersion": "keda.sh/v1alpha1", "kind": "ScaledJob",
            "metadata": {"name": cfg["name"].replace("_", "-"), "namespace": NS},
            "spec": {"jobTargetRef": {"backoffLimit": 0, "template": {"spec": {
                "restartPolicy": "Never",
                "containers": [{"name": "h", "image": img, "imagePullPolicy": "IfNotPresent",
                                "command": CMD[cfg["image"]], "args": [HANDLER]}]}}},
                "pollingInterval": cfg["poll"], "maxReplicaCount": 3,
                "successfulJobsHistoryLimit": 0, "failedJobsHistoryLimit": 2,
                "scalingStrategy": {"strategy": "default"},
                "triggers": [{"type": "redis", "metadata": {
                    "address": "redis.bench.svc.cluster.local:6379", "listName": "q", "listLength": "1"}}]}}


def worker_deploy(cfg):
    return {"apiVersion": "apps/v1", "kind": "Deployment",
            "metadata": {"name": "warmworker", "namespace": NS},
            "spec": {"replicas": 1, "selector": {"matchLabels": {"app": "warmworker"}},
                     "template": {"metadata": {"labels": {"app": "warmworker"}}, "spec": {"terminationGracePeriodSeconds": 0, "containers": [{
                         "name": "w", "image": IMAGES["slim"], "command": ["python", "-u", "/app/worker.py"],
                         "env": [{"name": "MODE", "value": cfg["mode"]}],
                         "volumeMounts": [{"name": "s", "mountPath": "/app"}]}],
                         "volumes": [{"name": "s", "configMap": {"name": "worker-script"}}]}}}}


def clean_jobs():
    kc("-n", NS, "delete", "jobs", "--all", "--cascade=foreground", "--wait=true", "--timeout=90s", check=False, timeout=150)
    for _ in range(30):
        if not kc("-n", NS, "get", "pods", "-l", "job-name", "-o", "name", check=False).strip():
            return
        time.sleep(1)


def drain_queues():
    kc("-n", NS, "exec", "deploy/pusher", "--", "python", "-c",
       "import socket;s=socket.create_connection(('redis',6379));"
       "[s.sendall(b'*2\\r\\n$3\\r\\nDEL\\r\\n$%d\\r\\n%s\\r\\n'%(len(k),k)) or s.recv(16) for k in (b'q',b'results')]",
       check=False)


def assert_no_strays(cfg):
    names = [x.split("/", 1)[1] for x in kc("-n", NS, "get", "pods", "-o", "name").split()]
    strays = [p for p in names if not p.startswith(("redis-", "pusher-", "watcher-"))]
    if strays:
        raise RuntimeError("stray pods present before %s: %s" % (cfg["name"], strays))


def valid_consumer(cfg, res):
    pod = res.get("pod") or ""
    if cfg["kind"] == "pool":
        return pod.startswith("warmworker-") and res.get("mode") == cfg["mode"]
    return pod.startswith(cfg["name"].replace("_", "-") + "-")


def run_config(cfg, n, warmups, log):
    rows = []
    assert_no_strays(cfg)
    poll = cfg.get("poll", 1)
    if cfg["kind"] == "job":
        kc("apply", "-f", "-", input=json.dumps(scaledjob(cfg)))
        kc("-n", NS, "wait", "--for=condition=Ready", "scaledjob/" + cfg["name"].replace("_", "-"), "--timeout=120s")
        time.sleep(max(2, poll + 1))
    else:
        kc("apply", "-f", "-", input=json.dumps(worker_deploy(cfg)))
        kc("-n", NS, "rollout", "status", "deploy/warmworker", "--timeout=180s")
        time.sleep(3)
    try:
        for i in range(-warmups, n):
            warm = i < 0
            if cfg["kind"] == "job":
                clean_jobs()
                if cfg["cold"] and not warm:
                    evict(cfg["image"])
            drain_queues()
            time.sleep(random.uniform(0, poll if cfg["kind"] == "job" else 1.5))  # randomize phase vs poll loop
            tid = "%s-%d-%d" % (cfg["name"], i, int(time.time() * 1000))
            sent = push(tid)
            res = pop_result(tid, timeout=poll + 240 if cfg["kind"] == "job" else 30)
            invalid = None
            if res and not valid_consumer(cfg, res):
                invalid = "wrong_consumer:%s" % res.get("pod"); log("  !! %s trial %d consumed by %s -> INVALID" % (cfg["name"], i, res.get("pod")))
                res = None
            row = dict(config=cfg["name"], trial=i, warmup=warm, tid=tid, t_send=sent["t_send"], result=res,
                       cold=cfg.get("cold", False), poll=cfg.get("poll"), image=cfg.get("image"), mode=cfg.get("mode"),
                       wall=datetime.datetime.utcnow().isoformat() + "Z", invalid=invalid)
            rows.append(row)
            if res:
                log("  %s trial %d%s: send->handler = %.0f ms" % (cfg["name"], i, " (warmup)" if warm else "",
                                                                  (res["t_start"] - sent["t_send"]) * 1000))
            else:
                log("  %s trial %d: NO RESULT (timeout)" % (cfg["name"], i))
    finally:
        if cfg["kind"] == "job":
            kc("-n", NS, "delete", "scaledjob", cfg["name"].replace("_", "-"), "--wait=true", check=False)
            clean_jobs()
        else:
            kc("-n", NS, "delete", "deploy", "warmworker", "--wait=true", check=False)
            kc("-n", NS, "wait", "--for=delete", "pod", "-l", "app=warmworker", "--timeout=90s", check=False, timeout=120)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--distroless", action="store_true")
    ap.add_argument("--seed", type=int, default=int(time.time()))
    a = ap.parse_args()
    n = 3 if a.quick else a.n
    random.seed(a.seed)
    os.makedirs(DATA, exist_ok=True)
    tag = ("quick_" if a.quick else "full_") + datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    trials_path = os.path.join(DATA, "trials_%s.jsonl" % tag)
    logf = open(os.path.join(DATA, "run_%s.log" % tag), "a")

    def log(m):
        line = "[%s] %s" % (datetime.datetime.utcnow().strftime("%H:%M:%S"), m)
        print(line, flush=True); logf.write(line + "\n"); logf.flush()

    cfgs = [c for c in CONFIGS if (not c.get("optional") or a.distroless or (a.only and c["name"] in a.only))]
    if a.only:
        cfgs = [c for c in CONFIGS if c["name"] in a.only]
    random.shuffle(cfgs)
    meta = dict(tag=tag, seed=a.seed, n=n, order=[c["name"] for c in cfgs],
                kubectl=kc("version", "--client", "-o", "json", check=False)[:400],
                keda_image=kc("get", "deploy", "-n", "keda", "keda-operator", "-o",
                              "jsonpath={.spec.template.spec.containers[0].image}", check=False),
                nodes=kc("get", "nodes", "-o", "name", check=False).split())
    json.dump(meta, open(os.path.join(DATA, "meta_%s.json" % tag), "w"), indent=1)
    log("run %s  n=%d  order=%s" % (tag, n, meta["order"]))
    for cfg in cfgs:
        log("config %s" % cfg["name"])
        try:
            rows = run_config(cfg, n, warmups=0 if cfg.get("cold") or cfg["kind"] == "pool" else 1, log=log)
        except Exception as e:
            log("  config %s FAILED: %s" % (cfg["name"], e)); rows = []
        with open(trials_path, "a") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        wl = kc("-n", NS, "logs", "deploy/watcher", "--tail=-1", check=False, timeout=120)
        open(os.path.join(DATA, "watcher_%s.jsonl" % tag), "w").write(wl)
    log("done. trials: %s" % trials_path)


if __name__ == "__main__":
    main()
