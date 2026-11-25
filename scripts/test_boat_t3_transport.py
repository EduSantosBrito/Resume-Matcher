"""Deterministic checks for job/thread isolation and quota-only fallback."""

import importlib.util
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest import TestCase, mock
from uuid import uuid4

spec = importlib.util.spec_from_file_location(
    "transport", Path(__file__).with_name("boat-t3-transport.py")
)
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)


class TransportTests(TestCase):
    def test_socket_survives_transport_restart_with_state_kept_separately(self) -> None:
        script = Path(transport.__file__)
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            state = Path(tmp) / "state"
            runtime = Path(tmp) / "run"
            runtime.mkdir(mode=0o700)
            sock = runtime / "model.sock"
            env = {
                **os.environ,
                "RESUME_T3_TRANSPORT_DIR": str(state),
                "RESUME_T3_SOCKET_DIR": str(runtime),
                "RESUME_T3_SOCKET": str(sock),
            }
            for attempt in range(2):
                with subprocess.Popen([sys.executable, script], env=env) as server:
                    try:
                        for _ in range(100):
                            if sock.is_socket() and server.poll() is None:
                                check = subprocess.run(
                                    [
                                        sys.executable,
                                        script.with_name("check-boat-t3-transport.py"),
                                    ],
                                    env=env,
                                    capture_output=True,
                                    check=False,
                                    timeout=5,
                                )
                                if check.returncode == 0:
                                    break
                            time.sleep(0.02)
                        else:
                            self.fail(f"Container probe failed on start {attempt + 1}")
                    finally:
                        server.terminate()
                with sqlite3.connect(state / "threads.sqlite") as db:
                    if attempt == 0:
                        db.execute(
                            "INSERT INTO threads VALUES ('fixture', 'thread', 0)"
                        )
                    self.assertEqual(
                        db.execute("SELECT COUNT(*) FROM threads").fetchone(), (1,)
                    )
            self.assertFalse((state / "socket").exists())

    def test_quota_retry_then_reuse(self) -> None:
        db = sqlite3.connect(":memory:")
        db.execute("create table threads(job primary key,thread,fallback)")
        req = {"job": str(uuid4()), "messages": []}
        ok = {"status": "completed", "threadId": "fallback", "reply": "ok"}
        with mock.patch.object(
            transport,
            "turn",
            side_effect=[
                {"status": "failed", "error": "Individual quota exceeded"},
                ok,
                ok,
                ok,
            ],
        ) as turn:
            transport.answer(db, req)
            transport.answer(db, req)
            transport.answer(db, {**req, "job": str(uuid4())})
        self.assertEqual(
            [c.args[:2] for c in turn.call_args_list],
            [(None, False), (None, True), ("fallback", 1), (None, False)],
        )

    def test_not_quota(self) -> None:
        for error in ("Authentication required", "timeout", "provider unavailable"):
            self.assertFalse(
                transport.quota_failure({"error": error, "status": "failed"})
            )
