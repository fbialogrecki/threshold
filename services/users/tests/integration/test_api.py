from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from users.domain.models import ApplicationUser, Page, PageMembership, PageMembershipRole
from users.main import app

TOKEN_HEADERS = {"X-Threshold-Internal-Token": "test-internal-token"}


def test_healthz() -> None:
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "users"}


def test_readyz_checks_database(session: Session) -> None:
    client = TestClient(app)
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "users"}


def test_current_profile_create_on_first_login(session: Session) -> None:
    client = TestClient(app)
    response = client.post(
        "/internal/v1/current-profile",
        headers=TOKEN_HEADERS,
        json={
            "authentik_subject": "ak-subject-1",
            "email": "person@example.test",
            "username": "person",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["authentik_subject"] == "ak-subject-1"
    assert body["user"]["email"] == "person@example.test"
    assert body["consumer_profile"]["display_name"] == "person"
    assert body["onboarding_preferences"]["city"] is None


def test_onboarding_preferences_update(session: Session) -> None:
    client = TestClient(app)
    profile_response = client.post(
        "/internal/v1/current-profile",
        headers=TOKEN_HEADERS,
        json={"authentik_subject": "ak-subject-2", "username": "another"},
    )
    user_id = profile_response.json()["user"]["id"]

    response = client.put(
        f"/internal/v1/users/{user_id}/onboarding-preferences",
        headers=TOKEN_HEADERS,
        json={"city": "Poznan", "preferred_scenes": "breakbeat", "onboarding_skipped": False},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["onboarding_preferences"]["city"] == "Poznan"
    assert body["onboarding_preferences"]["preferred_scenes"] == "breakbeat"
    assert body["onboarding_preferences"]["onboarding_skipped"] is False


def test_onboarding_preferences_ignore_deprecated_skip(session: Session) -> None:
    client = TestClient(app)
    profile_response = client.post(
        "/internal/v1/current-profile",
        headers=TOKEN_HEADERS,
        json={"authentik_subject": "ak-subject-skip", "username": "skipme"},
    )
    user_id = profile_response.json()["user"]["id"]

    response = client.put(
        f"/internal/v1/users/{user_id}/onboarding-preferences",
        headers=TOKEN_HEADERS,
        json={"city": None, "preferred_scenes": None, "onboarding_skipped": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["onboarding_preferences"]["city"] is None
    assert body["onboarding_preferences"]["preferred_scenes"] is None
    assert body["onboarding_preferences"]["onboarding_skipped"] is False


def test_onboarding_preferences_update_returns_404_for_unknown_user(session: Session) -> None:
    client = TestClient(app)
    response = client.put(
        "/internal/v1/users/00000000-0000-0000-0000-000000000000/onboarding-preferences",
        headers=TOKEN_HEADERS,
        json={"city": "Warsaw"},
    )
    assert response.status_code == 404


def test_page_membership_internal_endpoint_requires_token(session: Session) -> None:
    client = TestClient(app)
    response = client.get(
        "/internal/v1/pages/00000000-0000-0000-0000-000000000001/members/00000000-0000-0000-0000-000000000002"
    )
    assert response.status_code == 401


def test_page_membership_internal_endpoint_returns_role(session: Session) -> None:
    client = TestClient(app)
    user = ApplicationUser(id="00000000-0000-0000-0000-000000000002")
    page = Page(
        id="00000000-0000-0000-0000-000000000001",
        slug="warehouse",
        display_name="Warehouse",
    )
    session.add_all(
        [
            user,
            page,
            PageMembership(page_id=page.id, user_id=user.id, role=PageMembershipRole.editor),
        ]
    )
    session.commit()

    response = client.get(
        f"/internal/v1/pages/{page.id}/members/{user.id}",
        headers=TOKEN_HEADERS,
    )
    assert response.status_code == 200
    assert response.json() == {"role": "editor"}


def test_page_membership_internal_endpoint_denies_inactive_user(session: Session) -> None:
    client = TestClient(app)
    user = ApplicationUser(
        id="00000000-0000-0000-0000-000000000012",
        status="locked",
    )
    page = Page(
        id="00000000-0000-0000-0000-000000000011",
        slug="locked-warehouse",
        display_name="Locked Warehouse",
    )
    session.add_all(
        [
            user,
            page,
            PageMembership(page_id=page.id, user_id=user.id, role=PageMembershipRole.owner),
        ]
    )
    session.commit()

    locked = client.get(
        f"/internal/v1/pages/{page.id}/members/{user.id}",
        headers=TOKEN_HEADERS,
    )
    user.status = "deleted"
    session.commit()
    deleted = client.get(
        f"/internal/v1/pages/{page.id}/members/{user.id}",
        headers=TOKEN_HEADERS,
    )

    assert locked.status_code == 404
    assert locked.json() == {"detail": "not a member"}
    assert deleted.status_code == 404
    assert deleted.json() == {"detail": "not a member"}
