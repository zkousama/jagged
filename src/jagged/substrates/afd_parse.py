import re

from msgspec import Struct

INVISIBLE = dict.fromkeys(
    map(ord, "‎‏​‌‍­⁦⁧⁨⁩﻿"), None
)

RESULT_RE = re.compile(
    r"(?is)the result (?:of the (?:debate|discussion) )?was[:\s]*'''(?P<result>.+?)'''"
)
MAGIC_RE = re.compile(r"__[A-Z_]+__")
NON_ADMIN_RE = re.compile(r"(?i)WP:NACD|non-admin closure")

NORMAL = {
    "keep": "keep",
    "speedy keep": "keep",
    "delete": "delete",
    "speedy delete": "delete",
    "soft delete": "soft_delete",
    "redirect": "redirect",
    "merge": "merge",
    "no consensus": "no_consensus",
    "withdrawn": "withdrawn",
}


class Close(Struct, frozen=True):
    result: str
    normalized: str
    rationale: str
    non_admin: bool


def strip_invisibles(s: str) -> str:
    return s.translate(INVISIBLE)


def parse_close(wikitext: str) -> Close | None:
    text = strip_invisibles(wikitext)
    m = RESULT_RE.search(text)
    if not m:
        return None
    result = m.group("result").strip().strip(".").lower()
    tail = MAGIC_RE.sub("", text[m.end():])
    rationale = tail.split("\n", 1)[0].strip().lstrip(". ").strip()
    return Close(
        result=result,
        normalized=NORMAL.get(result, "other"),
        rationale=rationale,
        non_admin=bool(NON_ADMIN_RE.search(rationale)),
    )
