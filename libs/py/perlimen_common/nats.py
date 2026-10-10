def inject_traceparent(headers: dict[str, str], traceparent: str | None) -> dict[str, str]:
    if traceparent:
        headers["traceparent"] = traceparent
    return headers
