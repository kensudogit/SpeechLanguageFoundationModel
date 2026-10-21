from collections import Counter

_counts: Counter[str] = Counter()


def bump(name: str, n: int = 1) -> None:
    _counts[name] += n


def snapshot() -> dict:
    return {
        "transcribe": _counts["transcribe"],
        "turn": _counts["turn"],
        "ws_live": _counts["ws_live"],
        "ws_transcribe": _counts["ws_transcribe"],
        "denied_429": _counts["denied_429"],
        "denied_401": _counts["denied_401"],
        "note": "process_counters_not_sla",
    }
