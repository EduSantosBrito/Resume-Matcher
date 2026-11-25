# Resume Matcher on Boat

The app connects to the T3 adapter through a Unix socket. Keep the socket on
the VM's `/run` tmpfs. Boat can replace the filesystem backing `/home` while
an early-started service still holds its original listener. Keep the thread
mapping database in the existing persistent `t3-transport` directory.

In the Boat deployment's private Compose file, the `resume-matcher` service
uses the following mount and environment setting alongside its data volume.

```yaml
volumes:
  - /run/resume-t3-transport:/model:ro
environment:
  RESUME_T3_SOCKET: /model/model.sock
```

Install `resume-t3-transport.conf` in `/etc/tmpfiles.d/`. The early boot
tmpfiles service creates the directory with mode 0700 for the host user
whose UID matches the app container. Keep this directory across adapter
restarts so the container's bind mount continues to refer to it.

Install both `resume-t3-*.service` files in `/etc/systemd/system/` and both
Python scripts (`boat-t3-transport.py` and `check-boat-t3-transport.py`) in
`/home/user/boat-services/resume/native-t3/scripts/`. On an existing VM,
run `systemd-tmpfiles --create /etc/tmpfiles.d/resume-t3-transport.conf`
and `systemctl daemon-reload` as root. Enable and restart the transport,
then apply the Compose change to the app service with
`docker compose up -d --no-deps --no-build --pull never --wait resume-matcher`.
Enable and start `resume-t3-check.service` once the app container is ready.

The boot check sends a ping from inside the app container and runs an
authenticated, read-only query against the local T3 server. It discards the
query output, retries during startup and records the result in the system
journal. To repeat it, run
`systemctl start resume-t3-check.service` as root and inspect
`journalctl -b -u resume-t3-check.service`. A successful check verifies the
adapter connection and local T3 authentication. Provider authentication and
model quota are separate.
