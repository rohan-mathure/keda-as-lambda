import time, socket, json, os
t0 = time.time()  # handler start (after interpreter boot, ~20-30ms)
def enc(cmd):
    return ("*%d\r\n" % len(cmd) + "".join("$%d\r\n%s\r\n" % (len(c.encode()), c) for c in cmd)).encode()
s = socket.create_connection(("redis.bench.svc.cluster.local", 6379), timeout=15)
f = s.makefile("rb")
s.sendall(enc(["RPOP", "q"]))
h = f.readline()
pod = os.environ.get("HOSTNAME")
if h.startswith(b"$-1"):
    out = {"nil": True, "pod": pod, "t_start": t0}
else:
    n = int(h[1:]); body = f.read(n + 2)[:-2]
    out = json.loads(body); out.update(pod=pod, t_start=t0, t_popped=time.time())
s.sendall(enc(["RPUSH", "results", json.dumps(out)])); f.readline()
