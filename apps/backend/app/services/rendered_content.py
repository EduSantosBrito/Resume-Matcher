"""Project stored resume data onto content visible in the editor's PDF."""

from typing import Any

from app.services.ats_parse.roundtrip import CONDENSED_ORDER


def is_section_visible(resume: dict[str, Any], key: str) -> bool:
    for meta in resume.get("sectionMeta") or []:
        if isinstance(meta, dict) and meta.get("key") == key:
            return meta.get("isVisible", True) is not False
    return True


def rendered_content(resume: dict[str, Any]) -> dict[str, Any]:
    """Omit hidden sections and fields suppressed for condensed work entries."""
    content = {
        key: value
        for key, value in resume.items()
        if key != "sectionMeta" and is_section_visible(resume, key)
    }
    work = content.get("workExperience")
    if isinstance(work, list):
        content["workExperience"] = [
            {key: entry.get(key) for key in CONDENSED_ORDER}
            if isinstance(entry, dict) and entry.get("condensed")
            else entry
            for entry in work
        ]
    custom = content.get("customSections")
    if isinstance(custom, dict):
        content["customSections"] = {
            key: value
            for key, value in custom.items()
            if is_section_visible(resume, key)
        }
    return content
