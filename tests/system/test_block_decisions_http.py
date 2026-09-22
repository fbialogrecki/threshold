"""Canonical post-ack decisions over real HTTP and migrated PostgreSQL."""

from uuid import uuid4

import httpx

from .harness import Stack
from .test_blocks_http import register

URL = "/internal/v1/users/block-decisions"


def test_fresh_bidirectional_decisions_after_acknowledgement(http_stack: Stack) -> None:
    stack = http_stack
    with (
        httpx.Client(base_url=stack.urls["users"], trust_env=False, timeout=3) as viewer,
        httpx.Client(base_url=stack.urls["users"], trust_env=False, timeout=3) as target,
    ):
        a = register(viewer, f"decision_a_{uuid4().hex[:10]}")
        b = register(target, f"decision_b_{uuid4().hex[:10]}")
        missing = str(uuid4())
        headers = {"X-Threshold-Internal-Token": stack.token}
        payload = {"viewer_id": a["id"], "target_ids": [b["id"], missing, b["id"]]}
        for supplied in ({}, {"X-Threshold-Internal-Token": "invalid"}):
            assert viewer.post(URL, headers=supplied, json=payload).status_code == 401

        def check(allowed: bool) -> None:
            response = viewer.post(URL, headers=headers, json=payload)
            assert response.status_code == 200
            assert response.json() == {
                "viewer_id": a["id"],
                "decisions": [
                    {"target_id": b["id"], "allowed": allowed},
                    {"target_id": missing, "allowed": False},
                    {"target_id": b["id"], "allowed": allowed},
                ],
            }

        check(True)
        # Public acknowledgement commits before the next independent HTTP decision.
        assert viewer.post("/v1/me/blocks", json={"username": b["username"]}).status_code == 201
        check(False)
        assert viewer.delete(f"/v1/me/blocks/{b['username']}").status_code == 204
        check(True)
        assert target.post("/v1/me/blocks", json={"username": a["username"]}).status_code == 201
        check(False)
        assert target.delete(f"/v1/me/blocks/{a['username']}").status_code == 204
        check(True)
        with stack.connect("users", "users_runtime") as conn:
            conn.execute(
                "UPDATE application_users SET status = 'erasure_pending' WHERE id = %s", (b["id"],)
            )
        check(False)
        payload["viewer_id"] = missing
        response = viewer.post(URL, headers=headers, json=payload)
        assert response.status_code == 200
        assert response.json()["viewer_id"] == missing
        assert all(item["allowed"] is False for item in response.json()["decisions"])
