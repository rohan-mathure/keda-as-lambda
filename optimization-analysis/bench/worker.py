import time, socket, json, os
mode = os.environ.get("MODE", "blpop")   # blpop = blocking pop, poll1s = RPOP every 1s
def enc(cmd):
    return ("*%d\r\n" % len(cmd) + "".join("$%d\r\n%s\r\n" % (len(c.encode()), c) for c in cmd)).encode()
s = socket.create_connection(("redis.bench.svc.cluster.local", 6379))
f = s.makefile("rb")
def bulk():
    h = f.readline()
    n = int(h[1:])
    return None if n < 0 else f.read(n + 2)[:-2].decode()
def arr():
    h = f.readline()
    if h[:2] == b"*-": return None
    return [bulk() for _ in range(int(h[1:]))]
print("ready", flush=True)
while True:
    if mode == "blpop":
        s.sendall(enc(["BRPOP", "q", "0"])); r = arr(); body = r[1] if r else None
    else:
        s.sendall(enc(["RPOP", "q"])); body = bulk()
        if body is None:
            time.sleep(1.0); continue
    t = time.time()
    out = json.loads(body); out.update(pod=os.environ.get("HOSTNAME"), t_start=t, mode=mode)
    s.sendall(enc(["RPUSH", "results", json.dumps(out)])); f.readline()
