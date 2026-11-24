"""Offline contract checks: python3 -m unittest discover -s scripts -p test_boat_vacancy_worker.py"""

import json
import runpy
import sqlite3
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

worker = runpy.run_path(str(Path(__file__).with_name("boat-vacancy-worker.py")))


class RoutingTests(unittest.TestCase):
    def attempt(self, error: str, expected: list[str]) -> None:
        db = sqlite3.connect(":memory:")
        db.execute("create table requests (id, payload, status)")
        db.execute(
            "insert into requests values(?,?,?)",
            (
                "test",
                json.dumps(
                    {"master": {"personalInfo": {"email": "hidden@example.invalid"}}}
                ),
                "queued",
            ),
        )

        db.commit()

        def call(args: list[str], **kwargs: object) -> subprocess.CompletedProcess:
            self.assertNotIn(b"hidden@example.invalid", kwargs["input"])
            return subprocess.CompletedProcess(
                args, 1, json.dumps({"error": error}).encode()
            )

        with patch("subprocess.run", side_effect=call) as mock:
            worker["consume"](db)
        self.assertEqual(
            [c.args[0][c.args[0].index("--model") + 1] for c in mock.call_args_list],
            expected,
        )
        self.assertEqual(
            db.execute("select status,payload from requests").fetchone(),
            ("failed", None),
        )

    def test_quota_uses_argon_once(self) -> None:
        self.attempt(
            "Individual model quota exhausted",
            ["gemini-4-neon", "opencode-go/gemini-4-argon"],
        )

    def test_login_failure_does_not_change_provider(self) -> None:
        self.attempt("Please sign in", ["gemini-4-neon"])
