"""Check the configured Unix socket from the app container without calling a model."""

import json
import os
import socket

with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
    client.settimeout(5)
    client.connect(os.environ["RESUME_T3_SOCKET"])
    client.sendall(b'{"op":"ping"}\n')
    with client.makefile("rb") as stream:
        reply = json.loads(stream.readline(256))
    if reply != {"ok": True, "reply": "pong"}:
        raise SystemExit("Unexpected T3 transport reply")
print("T3 transport reachable from Resume Matcher")
