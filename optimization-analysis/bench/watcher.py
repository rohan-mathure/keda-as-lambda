"""In-cluster watcher: timestamps every Pod/Job/Event change in namespace `bench`
using the same clock as the handlers (all k3d nodes share the Docker VM clock)."""
import json, os, ssl, threading, time, urllib.request

HOST = os.environ["KUBERNETES_SERVICE_HOST"]
PORT = os.environ["KUBERNETES_SERVICE_PORT"]
SA = "/var/run/secrets/kubernetes.io/serviceaccount/"
TOKEN = open(SA + "token").read().strip()
CTX = ssl.create_default_context(cafile=SA + "ca.crt")
NS = "bench"
lock = threading.Lock()


def emit(rec):
    with lock:
        print(json.dumps(rec), flush=True)


def summarize(kind, ev_type, o, t):
    md = o.get("metadata", {})
    rec = {"t": t, "type": ev_type, "kind": kind, "name": md.get("name")}
    if kind == "Pod":
        st = o.get("status", {})
        cs = (st.get("containerStatuses") or [{}])[0].get("state", {})
        key = next(iter(cs), None)
        rec.update(job=(md.get("labels") or {}).get("job-name"),
                   node=o.get("spec", {}).get("nodeName"),
                   phase=st.get("phase"), cstate=key,
                   reason=(cs.get(key) or {}).get("reason") if key else None)
    elif kind == "Job":
        rec.update(succeeded=o.get("status", {}).get("succeeded"))
    elif kind == "Event":
        io = o.get("involvedObject", {})
        rec.update(pod=io.get("name"), ikind=io.get("kind"),
                   reason=o.get("reason"), message=o.get("message"))
    return rec


def watch(path, kind):
    while True:
        try:
            req = urllib.request.Request(
                "https://%s:%s%s?watch=1" % (HOST, PORT, path),
                headers={"Authorization": "Bearer " + TOKEN})
            with urllib.request.urlopen(req, context=CTX) as r:
                for line in r:
                    t = time.time()
                    ev = json.loads(line)
                    if ev.get("type") in ("ADDED", "MODIFIED", "DELETED"):
                        emit(summarize(kind, ev["type"], ev["object"], t))
        except Exception as e:  # reconnect
            emit({"t": time.time(), "err": str(e)})
            time.sleep(1)


for path, kind in [("/api/v1/namespaces/%s/pods" % NS, "Pod"),
                   ("/apis/batch/v1/namespaces/%s/jobs" % NS, "Job"),
                   ("/api/v1/namespaces/%s/events" % NS, "Event")]:
    threading.Thread(target=watch, args=(path, kind), daemon=True).start()
emit({"t": time.time(), "started": True})
while True:
    time.sleep(3600)
