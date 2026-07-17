class RateLimitNotConfigured(RuntimeError):
    pass


async def check_rate_limit(*, key: str, limit: int, window_seconds: int) -> None:
    """Placeholder for Dragonfly-backed rate limiting."""
    _ = (key, limit, window_seconds)
