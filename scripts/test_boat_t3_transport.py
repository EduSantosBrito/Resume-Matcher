"""Deterministic checks for job/thread isolation and quota-only fallback."""

import importlib.util
import sqlite3
from pathlib import Path
from unittest import TestCase, mock
from uuid import uuid4

spec = importlib.util.spec_from_file_location(
    "transport", Path(__file__).with_name("boat-t3-transport.py")
)
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)


class TransportTests(TestCase):
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
