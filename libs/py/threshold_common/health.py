from typing import Literal

HealthStatus = Literal["ok"]


def ok(service: str) -> dict[str, str]:
    return {"status": "ok", "service": service}
