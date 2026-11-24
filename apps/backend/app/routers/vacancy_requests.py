"""Private Boat workflow. The host worker is the only consumer."""

import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import settings
from app.database import db
from app.routers.resumes import _get_original_resume_data

router = APIRouter(prefix="/vacancy-requests")


class VacancyRequest(BaseModel):
    id: UUID
    description: str = Field(min_length=30, max_length=24000)


def queue() -> sqlite3.Connection:
    if os.getenv("RESUME_T3_ENABLED") != "1":
        raise HTTPException(404)
    directory = Path(settings.data_dir) / "vacancy-queue"
    directory.mkdir(mode=0o700, exist_ok=True)
    conn = sqlite3.connect(directory / "requests.sqlite", timeout=5)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, master TEXT NOT NULL, payload TEXT, status TEXT NOT NULL, resume TEXT)"
    )
    return conn


@router.get("")
async def recent_requests() -> list[dict]:
    with closing(queue()) as conn:
        conn.row_factory = sqlite3.Row
        return [
            dict(row)
            for row in conn.execute(
                "SELECT id,status,resume FROM requests ORDER BY rowid DESC LIMIT 8"
            )
        ]


@router.post("", status_code=202)
async def enqueue(body: VacancyRequest, request: Request) -> dict:
    if (
        request.headers.get("x-resume-workflow") != "1"
        or request.headers.get("sec-fetch-site") == "cross-site"
    ):
        raise HTTPException(403)
    with closing(queue()) as conn, conn:
        master = await db.get_master_resume()
        data = _get_original_resume_data(master) if master else None
        if not data:
            raise HTTPException(
                409, "Selecione um currículo master estruturado antes de gerar."
            )
        conn.execute("BEGIN IMMEDIATE")
        if not conn.execute(
            "SELECT 1 FROM requests WHERE id=?", (str(body.id),)
        ).fetchone():
            if (
                conn.execute(
                    "SELECT count(*) FROM requests WHERE status IN ('queued','neon','argon')"
                ).fetchone()[0]
                >= 3
            ):
                raise HTTPException(429, "Aguarde os pedidos em andamento.")
            conn.execute(
                "INSERT INTO requests VALUES (?,?,?,?,NULL)",
                (
                    str(body.id),
                    master["resume_id"],
                    json.dumps({"master": data, "vacancy": body.description}),
                    "queued",
                ),
            )
    return {"id": str(body.id)}
