import socket, time, json, sys
tid = sys.argv[1]
t = time.time()
msg = json.dumps({"id": tid, "t_send": t})
s = socket.create_connection(("redis", 6379))
cmd = ["LPUSH", "q", msg]
s.sendall(("*%d\r\n" % len(cmd) + "".join("$%d\r\n%s\r\n" % (len(c.encode()), c) for c in cmd)).encode())
s.recv(64)
print(json.dumps({"id": tid, "t_send": t}))
