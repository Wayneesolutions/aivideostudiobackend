import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

APPROVE_WORDS = [
    "haan", "han", "yes", "ok", "okay", "perfect", "go", "proceed",
    "aage", "badho", "approved", "approve", "looks good", "sahi hai",
    "theek", "done", "confirm", "accha", "bilkul",
]

CANCEL_WORDS = ["cancel", "band karo", "stop", "ruk", "nahi", "no"]


@dataclass
class ParsedAction:
    type: str
    shot_idx: int | None = None
    modifier: str | None = None
    extra: dict | None = None


def parse_intent(message: str, job_state: str) -> ParsedAction:
    msg = message.lower().strip()

    if any(w in msg for w in CANCEL_WORDS):
        return ParsedAction(type="cancel")

    if any(w in msg for w in APPROVE_WORDS) and "shot" not in msg:
        return ParsedAction(type="approve")

    if any(w in msg for w in ["music", "song", "gaana"]):
        return ParsedAction(type="change_music")

    if any(w in msg for w in ["square", "1:1", "16:9", "youtube"]):
        ratio = "1:1" if "square" in msg or "1:1" in msg else "16:9"
        return ParsedAction(type="change_ratio", extra={"ratio": ratio})

    shot_match = re.search(r"shot\s*(\d+)|clip\s*(\d+)", msg)
    if shot_match:
        idx = int(shot_match.group(1) or shot_match.group(2)) - 1
        modifier = re.sub(r"shot\s*\d+|clip\s*\d+", "", msg).strip()
        modifier = re.sub(r"[^a-z0-9 ]", "", modifier).strip()
        action_type = "regenerate_shot" if job_state == "FRAMES_READY" else "edit_shot"
        return ParsedAction(type=action_type, shot_idx=idx, modifier=modifier or None)

    logger.info(f"Could not parse: '{message}'")
    return ParsedAction(type="clarify")
