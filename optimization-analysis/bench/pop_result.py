import socket, sys, json
timeout = sys.argv[1]
s = socket.create_connection(("redis", 6379), timeout=int(timeout) + 15)
f = s.makefile("rb")
cmd = ["BRPOP", "results", timeout]
s.sendall(("*%d\r\n" % len(cmd) + "".join("$%d\r\n%s\r\n" % (len(c.encode()), c) for c in cmd)).encode())
h = f.readline()
if h[:2] == b"*-":
    print("TIMEOUT")
else:
    f.readline(); f.readline()  # "$1" and key
    n = int(f.readline()[1:]); print(f.read(n + 2)[:-2].decode())
