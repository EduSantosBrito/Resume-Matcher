"""Commit a T3 draft locally. No model-provided identifiers are accepted."""

import asyncio
import json
import sys
from contextlib import closing
from uuid import UUID

from pydantic import BaseModel, Field

from app.database import db
from app.routers.vacancy_requests import queue, _get_original_resume_data
from app.schemas import ResumeData


class Draft(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=4500)
    bullets: list[list[str]]
    cover_letter: str = Field(min_length=100, max_length=9000)


async def save(request_id: UUID, draft: Draft) -> None:
    with closing(queue()) as conn, conn:
        row = conn.execute(
            "SELECT master,payload FROM requests WHERE id=? AND status IN ('neon','argon')",
            (str(request_id),),
        ).fetchone()
        if not row:
            raise ValueError("request not running")
        original = json.loads(row[1])
        data = original["master"]
        source = await db.get_resume(row[0])
        if (
            not source
            or not source.get("is_master")
            or _get_original_resume_data(source) != data
        ):
            raise ValueError("master changed")
        entries = data.get("workExperience", [])
        if len(entries) != len(draft.bullets):
            raise ValueError("experience count changed")
        for entry, lines in zip(entries, draft.bullets, strict=True):
            if len(lines) != len(entry.get("description", [])) or any(
                not line.strip() or len(line) > 3500 or "<" in line for line in lines
            ):
                raise ValueError("invalid bullet list")
            entry["description"] = lines
        if "<" in draft.summary or "<" in draft.cover_letter:
            raise ValueError("expected plain text")
        data["summary"] = draft.summary
        ResumeData.model_validate(data)
        job = await db.create_job(original["vacancy"], resume_id=row[0])
        resume = await db.create_tailored_resume(
            request_id=str(request_id),
            original_resume_id=row[0],
            job_id=job["job_id"],
            resume_fields={
                "content": json.dumps(data),
                "content_type": "json",
                "filename": "tailored.json",
                "is_master": False,
                "parent_id": row[0],
                "processed_data": data,
                "processing_status": "ready",
                "title": draft.title,
                "cover_letter": draft.cover_letter,
            },
            improvements=[],
        )
        conn.execute(
            "UPDATE requests SET status='done',resume=?,payload=NULL WHERE id=?",
            (resume["resume_id"], str(request_id)),
        )


if __name__ == "__main__":
    asyncio.run(
        save(
            UUID(sys.argv[1]), Draft.model_validate_json(sys.stdin.buffer.read(200000))
        )
    )
