import collections
import re
from datetime import date

from jagged.items import Dual, Item, validate_item
from jagged.question import QuestionSpec
from jagged.substrates.afd_parse import Close, parse_close, strip_invisibles

CLOSE_BLOCK_RE = re.compile(r"(?is)\{\{\s*afd top.*?\}\}.*?(?=\n===)")
BOTTOM_RE = re.compile(r"(?is)\{\{\s*afd bottom\s*\}\}.*$")
BULLET_RE = re.compile(r"(?m)^\*+\s*'''")
SIG_RE = re.compile(r"\[\[User:[^\]]+\]\][^\n]*\(UTC\)")
TS_RE = re.compile(r"(\d{1,2}):(\d{2}), (\d{1,2}) (\w+) (\d{4}) \(UTC\)")
MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], start=1)}
NOM_RE = re.compile(r"(?is)\{\{la\|1=[^}]*\}\}\s*(?P<nom>.+?)(?=\n\*|\Z)")
STATE_CAP = 8000  # characters; keeps state well inside the 32k token ceiling
LISTING_PERIOD_DAYS = 7  # WP:AFD standard listing period
NUMBER_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven",
                "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen"]


def band_participants(n: int) -> str:
    if n <= 1:
        return "a single editor"
    if n <= 5:
        return "a handful of editors"
    return "many editors"


def _timestamps(text: str) -> list[date]:
    out = []
    for _h, _m, day, month, year in TS_RE.findall(text):
        if month in MONTHS:
            out.append(date(int(year), MONTHS[month], int(day)))
    return sorted(out)


def band_gap(days: int) -> str:
    """The gap in words, with the subtraction already done in code.

    Deliberately not "closed within a week". That phrasing answers the window
    question outright, which would make the baseline trivial and hand mode 3 an
    effect size that was really a giveaway. The model still has to weigh this
    against the seven days the instructions name.
    """
    if days <= 0:
        return "closed the same day it was nominated"
    word = NUMBER_WORDS[days] if days < len(NUMBER_WORDS) else str(days)
    return f"closed {word} day{'' if days == 1 else 's'} after it was nominated"


def _listing_length(body: str) -> tuple[Dual, int] | None:
    """Both forms of the same fact, so mode 3 swaps representation, not presence.

    `raw` carries the two dates and leaves the arithmetic to the model, which is
    the documented failure. `banded` carries the result of doing it in code,
    which is the documented remedy. One key either way.
    """
    stamps = _timestamps(body)
    if len(stamps) < 2:
        return None
    gap = (stamps[-1] - stamps[0]).days
    return Dual(
        raw=f"nominated {stamps[0].isoformat()}, closed {stamps[-1].isoformat()}",
        banded=band_gap(gap),
    ), gap


def stratum_for(participants: int, close: Close) -> str:
    if close.normalized in {"no_consensus"}:
        return "contested"
    return "thin_unanimous" if participants <= 3 else "well_attended"


class AfdSubstrate:
    name = "afd"

    def __init__(self, client):
        self.client = client
        self.dropped: collections.Counter = collections.Counter()

    def questions(self) -> dict[str, QuestionSpec]:
        """Verdict first: question-level arms rewrite whichever question leads.

        The window question is here so mode 3 has something to break. Asking for
        a date representation the judgment never reads would measure padding
        wearing mode 3's name.
        """
        return {
            "verdict": QuestionSpec(
                instructions=(
                    "The state describes a Wikipedia deletion discussion. "
                    "Answer whether the article was deleted."
                ),
                criteria={
                    "true": "The closing administrator deleted the article.",
                    "false": "The closing administrator kept the article.",
                },
                boundary="Treat a redirect or a merge as not deleted.",
            ),
            "window": QuestionSpec(
                instructions=(
                    "The state describes a Wikipedia deletion discussion. The "
                    "standard listing period is seven days. Answer whether this "
                    "discussion closed before that period had elapsed."
                ),
                criteria={
                    "true": "It closed sooner than seven days after nomination.",
                    "false": "It stayed open seven days or longer.",
                },
                boundary="A discussion closed on the seventh day itself closed on time, not early.",
            ),
        }

    def load(self, budget: int, dates: list[str] | None = None) -> list[Item]:
        dates = dates or ["2024 March 3"]
        items: list[Item] = []
        for date in dates:
            for title in self.client.log_titles(date):
                if len(items) >= budget:
                    return items
                item = self._build(title, self.client.wikitext(title))
                if item is not None:
                    items.append(item)
        return items

    def _build(self, title: str, wikitext: str) -> Item | None:
        close = parse_close(wikitext)
        if close is None:
            self.dropped["unparsed"] += 1
            return None
        if close.normalized not in {"keep", "delete"}:
            self.dropped[close.normalized] += 1
            return None

        body = BOTTOM_RE.sub("", CLOSE_BLOCK_RE.sub("", strip_invisibles(wikitext)))
        listing = _listing_length(body)
        if listing is None:
            # The window question has no answer without two timestamps, and an
            # item that can only answer half the questions would leave mode 3
            # scored on a different set of items than every other arm.
            self.dropped["undated"] += 1
            return None
        length, gap = listing
        nom_match = NOM_RE.search(body)
        nomination = (nom_match.group("nom") if nom_match else body[:600]).strip()
        participants = len(BULLET_RE.findall(body))
        signatures = " ".join(SIG_RE.findall(body))

        item = Item(
            id=f"afd:{title.removeprefix('Wikipedia:Articles for deletion/')}",
            core={"nomination": nomination[:STATE_CAP],
                  "discussion": body[:STATE_CAP]},
            context={"signatures": signatures[:STATE_CAP],
                     "procedural": "{{AFD help}} This debate is archived."},
            numeric={"participants": Dual(raw=str(participants),
                                             banded=band_participants(participants))},
            temporal={"listing_length": length},
            labels={"verdict": close.normalized == "delete",
                    "window": gap < LISTING_PERIOD_DAYS},
            stratum=stratum_for(participants, close),
        )
        validate_item(item)
        return item
