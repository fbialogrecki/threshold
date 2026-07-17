import re
from dataclasses import dataclass

MENTION_RE = re.compile(r"(?<![\w.@/`-])@([A-Za-z0-9_.-]{3,30})(?![\w.@-])")
EVENT_RE = re.compile(r"(?<![\w`-])#([a-z0-9][a-z0-9-]{1,158}[a-z0-9])(?![\w-])")


@dataclass(frozen=True)
class MentionCandidate:
    kind: str
    handle: str
    start_index: int
    end_index: int


def _inside_backticks(text: str, index: int) -> bool:
    return text[:index].count("`") % 2 == 1


def extract_mention_candidates(text: str) -> list[MentionCandidate]:
    candidates: list[MentionCandidate] = []
    for match in MENTION_RE.finditer(text):
        if _inside_backticks(text, match.start()):
            continue
        candidates.append(
            MentionCandidate(
                kind="profile",
                handle=match.group(1).lower(),
                start_index=match.start(),
                end_index=match.end(),
            )
        )
    for match in EVENT_RE.finditer(text):
        if _inside_backticks(text, match.start()):
            continue
        candidates.append(
            MentionCandidate(
                kind="event",
                handle=match.group(1).lower(),
                start_index=match.start(),
                end_index=match.end(),
            )
        )
    return sorted(candidates, key=lambda item: item.start_index)
