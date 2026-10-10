def clamp_limit(limit: int | None, *, default: int, maximum: int) -> int:
    return max(1, min(limit or default, maximum))
