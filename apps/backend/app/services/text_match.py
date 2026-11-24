"""Whole-term keyword matching shared by scoring, tailoring and refinement."""

import re
import unicodedata
from collections.abc import Iterable

# Treat orthographic hyphens like spaces, without flattening punctuation in
# identifiers (C++, C#, .NET) or crossing field/bullet boundaries.
_HYPHEN = re.compile(r"(?<=\w)[-‐‑](?=\w)")
_ELIGIBILITY = re.compile(
    r"\b(?:\d+\s*\+?\s*(?:years?|yrs?\.?|anos?)\b|"
    r"(?:years?|anos?) (?:of experience|de experi[eê]ncia)|"
    r"work authori[sz]ation|visa sponsorship|right to work|"
    r"(?:bachelor|master)[’']?s degree|university degree|high school diploma|"
    r"(?:eligible|authori[sz]ed) to work|"
    r"(?:office|onsite|on site) (?:attendance|presence|\d+ days?)|"
    r"hybrid (?:work|schedule)|in office|willing(?:ness)? to (?:relocate|travel)|"
    r"(?:english|portuguese|spanish) (?:fluency|proficiency|level)|"
    r"(?:fluency|proficiency|fluent) in (?:english|portuguese|spanish)|"
    r"(?:fluent|advanced|native) (?:english|portuguese|spanish)|"
    r"(?:inglês|português|espanhol) (?:fluente|avançado|nativo)|"
    r"(?:autorização para trabalhar|presença no escritório))\b"
)
_DUTY_STARTERS = frozenset(
    {"conduct", "design", "facilitate", "speak", "write", "build"}
)
SCORABLE_KEYWORD_FIELDS = ("required_skills", "preferred_skills", "keywords")


def _keyword_key(value: str) -> str:
    return _HYPHEN.sub(" ", unicodedata.normalize("NFC", value).casefold())


def distinct_keyword_terms(values: Iterable[object]) -> list[str]:
    """Keep distinct, short role terms; do not guess terms from prose."""
    terms: dict[str, str] = {}
    for value in values:
        if not isinstance(value, str):
            continue
        term = " ".join(value.split())
        key = _keyword_key(term)
        words = key.split()
        if (
            not words
            or len(words) > 7
            or len(term) > 80
            or not any(ch.isalnum() for ch in term)
            or (len(words) > 4 and words[0] in _DUTY_STARTERS)
            or _ELIGIBILITY.search(key)
        ):
            continue
        terms.setdefault(key, term)
    return list(terms.values())


# Han (including supplementary planes), Kana, and Hangul syllables/Jamo.
_CJK_CHAR_CLASS = (
    r"[ᄀ-ᇿ぀-ヿ㄰-㆏ㇰ-ㇿ"
    r"㐀-鿿ꥠ-꥿가-퟿豈-﫿"
    r"ｦ-ￜ\U0001b000-\U0001b16f\U00020000-\U0003ffff]"
)
_CJK_RE = re.compile(_CJK_CHAR_CLASS)


def keyword_in_text(keyword: str, text: str) -> bool:
    """Check for a CJK substring or a bounded non-CJK term in text.

    Han, Kana, and Hangul characters may adjoin Latin skills without whitespace,
    so they also form boundaries for adjacent Latin terms. Other word characters
    retain boundaries so 'python' does not match 'pythonic' and 'java' does not
    match 'javascript'.
    """
    normalized_keyword = " ".join(_keyword_key(keyword).split())
    if not normalized_keyword:
        return False
    normalized_text = _keyword_key(text)
    if _CJK_RE.search(normalized_keyword):
        return normalized_keyword in normalized_text
    escaped = r"[^\S\n]+".join(map(re.escape, normalized_keyword.split()))
    pattern = (
        rf"(?:(?<!\w)|(?<={_CJK_CHAR_CLASS}))"
        rf"{escaped}"
        rf"(?:(?![\w+#])|(?={_CJK_CHAR_CLASS}))"
    )
    return bool(re.search(pattern, normalized_text))


def normalize_skill_key(skill: str) -> str:
    """Normalize a skill for case-insensitive comparisons."""
    return re.sub(r"\s+", " ", skill.strip()).casefold()
