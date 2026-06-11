from __future__ import annotations

import re


def normalize_pick_status(status: str | None) -> str:
    if not status:
        return ""
    match = re.match(r"^(active|watch|closed|completed|blocked)", status.strip())
    if match:
        return match.group(1)
    return status.strip()
