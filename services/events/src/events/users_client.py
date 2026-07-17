import logging
from urllib.parse import quote

import httpx

from events.settings import Settings

logger = logging.getLogger(__name__)


def check_page_role(settings: Settings, page_id: str, user_id: str) -> str | None:
    try:
        page = quote(page_id, safe="")
        user = quote(user_id, safe="")
        resp = httpx.get(
            f"{settings.users_base_url.rstrip('/')}/internal/v1/pages/{page}/members/{user}",
            headers={"X-Threshold-Internal-Token": settings.threshold_internal_token or ""},
            timeout=3.0,
        )
        if resp.status_code == 200:
            role: str | None = resp.json().get("role")
            return role
        return None
    except Exception:
        logger.exception("check_page_role failed", extra={"page_id": page_id, "user_id": user_id})
        return None


def get_artist_ref(settings: Settings, artist_user_id: str) -> dict[str, str] | None:
    try:
        artist = quote(artist_user_id, safe="")
        resp = httpx.get(
            f"{settings.users_base_url.rstrip('/')}/internal/v1/artist-profiles/{artist}",
            headers={"X-Threshold-Internal-Token": settings.threshold_internal_token or ""},
            timeout=3.0,
        )
        if resp.status_code == 200:
            body = resp.json()
            if isinstance(body, dict):
                return {
                    "artist_profile_id": str(body.get("artist_profile_id", artist_user_id)),
                    "user_id": str(body.get("user_id", body.get("owner_user_id", ""))),
                    "owner_user_id": str(body.get("owner_user_id", body.get("user_id", ""))),
                    "username": str(body.get("username", "")),
                    "display_name": str(body.get("display_name", "")),
                    "target_url": str(body.get("target_url", "")),
                }
        return None
    except Exception:
        logger.exception("get_artist_ref failed", extra={"artist_user_id": artist_user_id})
        return None


def get_artist_refs(settings: Settings, artist_profile_ids: list[str]) -> dict[str, dict[str, str]]:
    ids = list(dict.fromkeys(artist_profile_ids))[:100]
    if not ids:
        return {}
    try:
        resp = httpx.post(
            f"{settings.users_base_url.rstrip('/')}/internal/v1/artist-profiles/batch",
            headers={"X-Threshold-Internal-Token": settings.threshold_internal_token or ""},
            json={"artist_profile_ids": ids},
            timeout=3.0,
        )
        if resp.status_code != 200:
            return {}
        return {
            str(item["artist_profile_id"]): {
                "artist_profile_id": str(item["artist_profile_id"]),
                "user_id": str(item["user_id"]),
                "owner_user_id": str(item["owner_user_id"]),
                "username": str(item["username"]),
                "display_name": str(item["display_name"]),
                "target_url": str(item["target_url"]),
            }
            for item in resp.json()
            if isinstance(item, dict) and item.get("artist_profile_id")
        }
    except Exception:
        logger.exception("get_artist_refs failed", extra={"artist_count": len(ids)})
        return {}


def get_active_user_refs(settings: Settings, user_ids: list[str]) -> dict[str, dict[str, str]]:
    ids = list(dict.fromkeys(user_ids))
    if not ids:
        return {}
    try:
        refs: dict[str, dict[str, str]] = {}
        for offset in range(0, len(ids), 100):
            resp = httpx.post(
                f"{settings.users_base_url.rstrip('/')}/internal/v1/users/active-refs",
                headers={"X-Threshold-Internal-Token": settings.threshold_internal_token or ""},
                json={"user_ids": ids[offset : offset + 100]},
                timeout=3.0,
            )
            if resp.status_code != 200:
                return {}
            refs.update(
                {
                    str(item["id"]): {
                        "user_id": str(item["id"]),
                        "username": str(item["username"]),
                        "display_name": str(item["display_name"]),
                    }
                    for item in resp.json()
                    if isinstance(item, dict)
                    and item.get("id")
                    and item.get("username")
                    and item.get("display_name")
                }
            )
        return refs
    except Exception:
        logger.exception("get_active_user_refs failed", extra={"user_count": len(ids)})
        return {}


def get_user_by_username(settings: Settings, username: str) -> dict[str, str] | None:
    try:
        handle = quote(username, safe="")
        resp = httpx.get(
            f"{settings.users_base_url.rstrip('/')}/internal/v1/mention-targets/profiles/{handle}",
            headers={"X-Threshold-Internal-Token": settings.threshold_internal_token or ""},
            timeout=3.0,
        )
        if resp.status_code == 200:
            body = resp.json()
            user_id = body.get("recipient_user_id") or body.get("target_id")
            if user_id:
                return get_active_user_refs(settings, [str(user_id)]).get(str(user_id))
        return None
    except Exception:
        logger.exception("get_user_by_username failed", extra={"username": username})
        return None


def notify_user(
    settings: Settings,
    *,
    recipient_user_id: str,
    actor_user_id: str | None,
    event_type: str,
    target_type: str,
    target_id: str,
    target_url: str,
    title: str,
    body: str | None,
    dedupe_key: str,
    metadata: dict[str, str | int | bool | None],
) -> bool:
    try:
        resp = httpx.post(
            f"{settings.users_base_url.rstrip('/')}/internal/v1/notifications",
            headers={"X-Threshold-Internal-Token": settings.threshold_internal_token or ""},
            json={
                "recipient_user_id": recipient_user_id,
                "actor_user_id": actor_user_id,
                "type": event_type,
                "target_type": target_type,
                "target_id": target_id,
                "target_url": target_url,
                "title": title,
                "body": body,
                "dedupe_key": dedupe_key,
                "metadata": metadata,
            },
            timeout=3.0,
        )
        return 200 <= resp.status_code < 300
    except Exception:
        logger.exception(
            "notify_user failed",
            extra={
                "recipient_user_id": recipient_user_id,
                "target_type": target_type,
                "target_id": target_id,
            },
        )
        return False
