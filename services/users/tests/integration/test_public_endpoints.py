from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from users.api import routes
from users.domain.models import (
    ApplicationUser,
    ArtistProfile,
    AuthAuditLog,
    ConsumerProfile,
    ContentReport,
    NotificationEvent,
    NotificationPreference,
    Page,
    PageMembership,
    PageMembershipRole,
    PageResidency,
    SafetyAuditLog,
    UserBlock,
)
from users.main import app


def test_get_public_profile_success(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(app)

    def _validate(
        _settings: Any, *, asset_id: str, owner_user_id: str, allowed_contexts: set[str]
    ) -> None:
        return None

    monkeypatch.setattr(routes, "validate_avatar_asset", _validate)

    # 1. Register a user (defaults to consumer)
    response = client.post(
        "/v1/auth/register",
        json={
            "email": "pubconsumer@example.test",
            "username": "pubconsumer",
            "password": "StrongPass123!",
            "display_name": "Pub Consumer display",
        },
    )
    assert response.status_code == 201
    user_id = response.json()["user"]["id"]
    user = session.get(ApplicationUser, user_id)
    assert user is not None
    assert user.consumer_profile is not None
    user.consumer_profile.avatar_media_asset_id = "asset-user-avatar"
    session.commit()

    # 2. Get public profile
    response = client.get("/v1/profiles/pubconsumer")
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "consumer"
    assert body["username"] == "pubconsumer"
    assert body["display_name"] == "Pub Consumer display"
    assert body["avatar_media_asset_id"] == "asset-user-avatar"
    assert "email" not in body  # NO PII!
    assert "email_normalized" not in body
    assert "authentik_subject" not in body
    assert "identity_source" not in body
    assert "status" not in body
    assert "deleted_at" not in body
    assert "owner_user_id" not in body
    assert "bucket" not in body
    assert "checksum_sha256" not in body
    assert body["follower_count"] == 0

    # 3. Create artist profile for user
    # We need to authenticate (using cookies) to create artist profile
    client2 = TestClient(app)
    # Login first
    login_resp = client2.post(
        "/v1/auth/login", json={"email_or_username": "pubconsumer", "password": "StrongPass123!"}
    )
    assert login_resp.status_code == 200

    art_resp = client2.post(
        "/v1/me/artist",
        json={
            "role": "Live Act",
            "location": "Berlin",
            "links": [{"label": "Resident Advisor", "url": "https://ra.co/pubconsumer"}],
        },
    )
    assert art_resp.status_code == 200

    # 4. Get public profile again, should be artist now
    response = client.get("/v1/profiles/pubconsumer")
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "artist"
    assert body["artist_profile_id"]
    assert body["role"] == "Live Act"
    assert body["location"] == "Berlin"
    assert body["links"] == [{"label": "Resident Advisor", "url": "https://ra.co/pubconsumer"}]


def test_accepted_residency_is_public_on_artist_and_page_only(session: Session) -> None:
    club_owner = ApplicationUser(
        id="owner-public-residency",
        username="clubowner",
        username_normalized="clubowner",
        consumer_profile=ConsumerProfile(display_name="Club Owner"),
    )
    accepted_artist = ApplicationUser(
        id="artist-public-residency",
        username="residentdj",
        username_normalized="residentdj",
        consumer_profile=ConsumerProfile(display_name="Resident DJ"),
        artist_profile=ArtistProfile(id="artist-profile-accepted", role="DJ"),
    )
    pending_artist = ApplicationUser(
        id="artist-pending-residency",
        username="pendingdj",
        username_normalized="pendingdj",
        consumer_profile=ConsumerProfile(display_name="Pending DJ"),
        artist_profile=ArtistProfile(id="artist-profile-pending", role="DJ"),
    )
    rejected_artist = ApplicationUser(
        id="artist-rejected-residency",
        username="rejecteddj",
        username_normalized="rejecteddj",
        consumer_profile=ConsumerProfile(display_name="Rejected DJ"),
        artist_profile=ArtistProfile(id="artist-profile-rejected", role="DJ"),
    )
    page = Page(slug="residency-room", display_name="Residency Room", page_type="club")
    session.add_all([club_owner, accepted_artist, pending_artist, rejected_artist, page])
    session.flush()
    session.add_all(
        [
            PageResidency(
                page_id=page.id,
                artist_user_id=accepted_artist.id,
                invited_by_user_id=club_owner.id,
                status="accepted",
            ),
            PageResidency(
                page_id=page.id,
                artist_user_id=pending_artist.id,
                invited_by_user_id=club_owner.id,
                status="pending",
            ),
            PageResidency(
                page_id=page.id,
                artist_user_id=rejected_artist.id,
                invited_by_user_id=club_owner.id,
                status="rejected",
            ),
        ]
    )
    session.commit()

    client = TestClient(app)
    artist_response = client.get("/v1/profiles/residentdj")
    pending_response = client.get("/v1/profiles/pendingdj")
    page_response = client.get("/v1/pages/residency-room")

    assert artist_response.status_code == 200
    assert artist_response.json()["residencies"] == [
        {
            "page_slug": "residency-room",
            "page_name": "Residency Room",
            "page_type": "club",
            "target_url": "/pages/residency-room",
        }
    ]
    assert pending_response.status_code == 200
    assert pending_response.json()["residencies"] == []
    assert page_response.status_code == 200
    assert page_response.json()["residents"] == [
        {
            "username": "residentdj",
            "display_name": "Resident DJ",
            "role": "DJ",
            "target_url": "/u/residentdj",
        }
    ]


def test_page_owner_invites_artist_and_artist_accepts_residency(session: Session) -> None:
    owner = TestClient(app)
    artist = TestClient(app)
    owner_register = owner.post(
        "/v1/auth/register",
        json={
            "email": "res-owner@example.test",
            "username": "resowner",
            "password": "StrongPass123!",
        },
    )
    assert owner_register.status_code == 201
    owner_id = owner_register.json()["user"]["id"]
    artist_register = artist.post(
        "/v1/auth/register",
        json={
            "email": "res-artist@example.test",
            "username": "resartist",
            "password": "StrongPass123!",
        },
    )
    assert artist_register.status_code == 201
    artist_id = artist_register.json()["user"]["id"]
    assert artist.post("/v1/me/artist", json={"role": "DJ", "links": []}).status_code == 200
    create_page = owner.post(
        "/v1/pages",
        json={"slug": "resident-club", "display_name": "Resident Club", "page_type": "club"},
    )
    assert create_page.status_code == 201
    page_id = create_page.json()["id"]

    invite = owner.post("/v1/pages/resident-club/residency-invitations/resartist")
    accept = artist.post(f"/v1/me/residencies/{invite.json()['id']}/accept")

    assert invite.status_code == 201
    assert invite.json()["status"] == "pending"
    assert accept.status_code == 200
    assert accept.json()["status"] == "accepted"
    assert (
        session.scalar(select(PageResidency).where(PageResidency.page_id == page_id))
        is not None
    )
    notifications = session.scalars(
        select(NotificationEvent).order_by(NotificationEvent.created_at)
    ).all()
    assert [
        (row.user_id, row.event_type)
        for row in notifications
        if row.event_type.startswith("residency.")
    ] == [
        (artist_id, "residency.invited"),
        (owner_id, "residency.accepted"),
    ]
    audit_actions = session.scalars(
        select(SafetyAuditLog.action).where(SafetyAuditLog.target_type == "residency")
    ).all()
    assert audit_actions == ["residency.invited", "residency.accepted"]


def test_residency_invite_role_matrix_and_no_self_escalation(session: Session) -> None:
    owner = TestClient(app)
    admin = TestClient(app)
    editor = TestClient(app)
    artist = TestClient(app)
    owner_register = owner.post(
        "/v1/auth/register",
        json={
            "email": "matrix-owner@example.test",
            "username": "matrixowner",
            "password": "StrongPass123!",
        },
    )
    admin_register = admin.post(
        "/v1/auth/register",
        json={
            "email": "matrix-admin@example.test",
            "username": "matrixadmin",
            "password": "StrongPass123!",
        },
    )
    editor_register = editor.post(
        "/v1/auth/register",
        json={
            "email": "matrix-editor@example.test",
            "username": "matrixeditor",
            "password": "StrongPass123!",
        },
    )
    artist_register = artist.post(
        "/v1/auth/register",
        json={
            "email": "matrix-artist@example.test",
            "username": "matrixartist",
            "password": "StrongPass123!",
        },
    )
    assert owner_register.status_code == 201
    assert admin_register.status_code == 201
    assert editor_register.status_code == 201
    assert artist_register.status_code == 201
    assert artist.post("/v1/me/artist", json={"role": "DJ", "links": []}).status_code == 200
    page_response = owner.post(
        "/v1/pages",
        json={"slug": "matrix-club", "display_name": "Matrix Club", "page_type": "club"},
    )
    assert page_response.status_code == 201
    assert (
        owner.put("/v1/pages/matrix-club/members/matrixadmin", json={"role": "admin"}).status_code
        == 200
    )
    assert (
        owner.put("/v1/pages/matrix-club/members/matrixeditor", json={"role": "editor"}).status_code
        == 200
    )

    editor_invite = editor.post("/v1/pages/matrix-club/residency-invitations/matrixartist")
    artist_initiated = artist.post("/v1/pages/matrix-club/residency-invitations/matrixartist")
    admin_invite = admin.post("/v1/pages/matrix-club/residency-invitations/matrixartist")
    reject = artist.post(f"/v1/me/residencies/{admin_invite.json()['id']}/reject")

    assert editor_invite.status_code == 403
    assert artist_initiated.status_code == 403
    assert admin_invite.status_code == 201
    assert reject.status_code == 200
    assert reject.json()["status"] == "rejected"


def test_public_profile_hides_unvalidated_legacy_avatar(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/auth/register",
        json={
            "email": "legacy-avatar@example.test",
            "username": "legacyavatar",
            "password": "StrongPass123!",
        },
    )
    assert response.status_code == 201
    user = session.get(ApplicationUser, response.json()["user"]["id"])
    assert user is not None
    assert user.consumer_profile is not None
    user.consumer_profile.avatar_media_asset_id = "legacy-unsafe-asset"
    session.commit()

    def _validate(
        _settings: Any, *, asset_id: str, owner_user_id: str, allowed_contexts: set[str]
    ) -> None:
        raise routes.MediaAssetValidationError("media validation failed")  # type: ignore[attr-defined]

    monkeypatch.setattr(routes, "validate_avatar_asset", _validate)

    public_response = client.get("/v1/profiles/legacyavatar")

    assert public_response.status_code == 200
    assert public_response.json()["avatar_media_asset_id"] is None


def test_get_public_profile_not_found(session: Session) -> None:
    client = TestClient(app)
    response = client.get("/v1/profiles/nonexistentuser")
    assert response.status_code == 404
    assert response.json()["detail"] == "profile not found"


def test_get_public_profile_deleted(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr("users.api.routes.anonymize_social_author", lambda *_args: None)
    monkeypatch.setattr("users.api.routes.erase_events_account", lambda *_args: None)
    monkeypatch.setattr("users.api.routes.erase_media_assets", lambda *_args: None)

    # Register and delete
    reg_resp = client.post(
        "/v1/auth/register",
        json={
            "email": "deleted@example.test",
            "username": "deleteduser",
            "password": "StrongPass123!",
        },
    )
    assert reg_resp.status_code == 201

    # Delete account
    del_resp = client.delete("/v1/me")
    assert del_resp.status_code == 204

    # Query public profile, should return 404
    response = client.get("/v1/profiles/deleteduser")
    assert response.status_code == 404


def test_get_public_page_success(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(app)

    def _validate(
        _settings: Any, *, asset_id: str, owner_user_id: str, allowed_contexts: set[str]
    ) -> None:
        return None

    monkeypatch.setattr(routes, "validate_avatar_asset", _validate)

    # Seed a page
    page = Page(
        slug="club-tresor",
        display_name="Tresor Berlin",
        page_type="club",
        city="Berlin",
        about="Legendary techno club",
        links=[{"label": "Website", "url": "https://tresorberlin.de"}],
        avatar_media_asset_id="asset-page-avatar",
        avatar_media_owner_user_id="page-owner-id",
    )
    session.add(page)
    session.commit()

    response = client.get("/v1/pages/club-tresor")
    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == "club-tresor"
    assert body["display_name"] == "Tresor Berlin"
    assert body["page_type"] == "club"
    assert body["city"] == "Berlin"
    assert body["about"] == "Legendary techno club"
    assert body["links"] == [{"label": "Website", "url": "https://tresorberlin.de"}]
    assert body["avatar_media_asset_id"] == "asset-page-avatar"
    assert "owner_user_id" not in body
    assert "bucket" not in body
    assert "checksum_sha256" not in body
    assert body["follower_count"] == 0
    assert body["is_following"] is False


def test_patch_public_page_avatar_requires_membership_and_valid_media(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(app)
    register = client.post(
        "/v1/auth/register",
        json={
            "email": "page-owner@example.test",
            "username": "pageowner",
            "password": "StrongPass123!",
        },
    )
    assert register.status_code == 201
    user_id = register.json()["user"]["id"]
    page = Page(slug="owned-page", display_name="Owned Page", page_type="club")
    session.add(page)
    session.flush()
    session.add(PageMembership(page_id=page.id, user_id=user_id, role=PageMembershipRole.editor))
    session.commit()

    calls = []

    def _validate(
        _settings: Any, *, asset_id: str, owner_user_id: str, allowed_contexts: set[str]
    ) -> None:
        calls.append((asset_id, owner_user_id, allowed_contexts))

    monkeypatch.setattr(routes, "validate_avatar_asset", _validate)
    response = client.patch(
        "/v1/pages/owned-page",
        json={"avatar_media_asset_id": "asset-page-owned"},
    )

    assert response.status_code == 200
    assert response.json()["avatar_media_asset_id"] == "asset-page-owned"
    assert calls == [
        ("asset-page-owned", user_id, {"page_avatar"}),
        ("asset-page-owned", user_id, {"page_avatar"}),
    ]


def test_patch_public_page_avatar_forbidden_without_membership(session: Session) -> None:
    client = TestClient(app)
    register = client.post(
        "/v1/auth/register",
        json={
            "email": "no-page-role@example.test",
            "username": "nopagerole",
            "password": "StrongPass123!",
        },
    )
    assert register.status_code == 201
    session.add(Page(slug="other-page", display_name="Other Page", page_type="club"))
    session.commit()

    response = client.patch(
        "/v1/pages/other-page",
        json={"avatar_media_asset_id": "asset-page-owned"},
    )

    assert response.status_code == 403


def test_search_entities(session: Session) -> None:
    client = TestClient(app)

    # Seed users and pages
    u1 = ApplicationUser(
        email="s1@example.test",
        username="searchuser",
        username_normalized="searchuser",
        consumer_profile=ConsumerProfile(display_name="Search User display"),
    )
    p1 = Page(
        slug="searchpage",
        display_name="Search Page display",
        page_type="collective",
        city="Warsaw",
    )
    session.add_all([u1, p1])
    session.commit()

    # 1. Search without filters, should return both
    response = client.get("/v1/search?q=search")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    handles = {item["handle"] for item in body}
    assert "searchuser" in handles
    assert "searchpage" in handles

    # 2. Search profiles only
    response = client.get("/v1/search?q=search&type=profiles")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["handle"] == "searchuser"
    assert body[0]["type"] == "consumer"

    # 3. Search pages only
    response = client.get("/v1/search?q=search&type=pages")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["handle"] == "searchpage"
    assert body[0]["type"] == "collective"


def test_owner_can_create_page_and_manage_editor_membership(session: Session) -> None:
    owner = TestClient(app)
    owner_register = owner.post(
        "/v1/auth/register",
        json={
            "email": "owner-flow@example.test",
            "username": "ownerflow",
            "password": "StrongPass123!",
        },
    )
    assert owner_register.status_code == 201
    owner_id = owner_register.json()["user"]["id"]
    member = TestClient(app)
    member_register = member.post(
        "/v1/auth/register",
        json={
            "email": "page-editor@example.test",
            "username": "pageeditor",
            "password": "StrongPass123!",
        },
    )
    assert member_register.status_code == 201
    member_id = member_register.json()["user"]["id"]

    create_response = owner.post(
        "/v1/pages",
        json={
            "slug": "mvp-club",
            "display_name": "MVP Club",
            "page_type": "club",
            "city": "Wrocław",
            "about": "Basement pressure",
            "links": [{"label": "Site", "url": "https://mvp.example"}],
        },
    )

    assert create_response.status_code == 201
    assert create_response.json()["slug"] == "mvp-club"
    page = session.scalar(select(Page).where(Page.slug == "mvp-club"))
    assert page is not None
    owner_membership = session.scalar(
        select(PageMembership).where(
            PageMembership.page_id == page.id,
            PageMembership.user_id == owner_id,
        )
    )
    assert owner_membership is not None
    assert owner_membership.role == PageMembershipRole.owner

    add_member = owner.put("/v1/pages/mvp-club/members/pageeditor", json={"role": "editor"})

    assert add_member.status_code == 200
    assert add_member.json() == {"role": "editor"}
    member_membership = session.scalar(
        select(PageMembership).where(
            PageMembership.page_id == page.id,
            PageMembership.user_id == member_id,
        )
    )
    assert member_membership is not None
    assert member_membership.role == PageMembershipRole.editor
    audit_events = session.scalars(
        select(AuthAuditLog.event_type).where(AuthAuditLog.user_id == owner_id)
    ).all()
    assert "page.created" in audit_events
    assert "page.member_upserted" in audit_events
    notifications = session.scalars(
        select(NotificationEvent).where(NotificationEvent.user_id == member_id)
    ).all()
    assert [event.event_type for event in notifications] == ["page.member_upserted"]
    assert notifications[0].payload == {
        "page_id": page.id,
        "page_slug": "mvp-club",
        "page_name": "MVP Club",
        "page_type": "club",
        "role": "editor",
    }

    managed_pages = owner.get("/v1/me/pages")
    assert managed_pages.status_code == 200
    assert managed_pages.json()[0]["id"] == page.id
    assert managed_pages.json()[0]["role"] == "owner"


def test_page_member_management_protects_owner_and_blocks_editor_escalation(
    session: Session,
) -> None:
    owner = TestClient(app)
    owner_register = owner.post(
        "/v1/auth/register",
        json={
            "email": "owner-protect@example.test",
            "username": "ownerprotect",
            "password": "StrongPass123!",
        },
    )
    assert owner_register.status_code == 201
    owner_id = owner_register.json()["user"]["id"]
    editor = TestClient(app)
    editor_register = editor.post(
        "/v1/auth/register",
        json={
            "email": "editor-protect@example.test",
            "username": "editorprotect",
            "password": "StrongPass123!",
        },
    )
    assert editor_register.status_code == 201
    editor_id = editor_register.json()["user"]["id"]
    target = TestClient(app)
    target_register = target.post(
        "/v1/auth/register",
        json={
            "email": "target-protect@example.test",
            "username": "targetprotect",
            "password": "StrongPass123!",
        },
    )
    assert target_register.status_code == 201
    page = Page(slug="protected-page", display_name="Protected Page", page_type="club")
    session.add(page)
    session.flush()
    session.add_all(
        [
            PageMembership(page_id=page.id, user_id=owner_id, role=PageMembershipRole.owner),
            PageMembership(page_id=page.id, user_id=editor_id, role=PageMembershipRole.editor),
        ]
    )
    session.commit()

    editor_add = editor.put(
        "/v1/pages/protected-page/members/targetprotect", json={"role": "admin"}
    )
    owner_role_change = owner.put(
        "/v1/pages/protected-page/members/ownerprotect", json={"role": "editor"}
    )
    owner_delete = owner.delete("/v1/pages/protected-page/members/ownerprotect")
    invalid_owner_grant = owner.put(
        "/v1/pages/protected-page/members/targetprotect", json={"role": "owner"}
    )

    assert editor_add.status_code == 403
    assert owner_role_change.status_code == 400
    assert owner_delete.status_code == 400
    assert invalid_owner_grant.status_code == 422


def test_user_can_report_profile_and_page_with_private_reporter_data(session: Session) -> None:
    reporter = TestClient(app)
    target = TestClient(app)
    owner = TestClient(app)
    reporter_register = reporter.post(
        "/v1/auth/register",
        json={
            "email": "reporter@example.test",
            "username": "reporter",
            "password": "StrongPass123!",
        },
    )
    assert reporter_register.status_code == 201
    reporter_id = reporter_register.json()["user"]["id"]
    assert (
        target.post(
            "/v1/auth/register",
            json={
                "email": "reported@example.test",
                "username": "reported",
                "password": "StrongPass123!",
            },
        ).status_code
        == 201
    )
    assert (
        owner.post(
            "/v1/auth/register",
            json={
                "email": "owner-report@example.test",
                "username": "ownerreport",
                "password": "StrongPass123!",
            },
        ).status_code
        == 201
    )
    page_response = owner.post(
        "/v1/pages",
        json={"slug": "report-page", "display_name": "Report Page", "page_type": "club"},
    )
    assert page_response.status_code == 201

    profile_report = reporter.post(
        "/v1/reports",
        json={
            "target_type": "profile",
            "target_handle": "reported",
            "reason": "harassment",
            "note": "dm spam",
        },
    )
    page_report = reporter.post(
        "/v1/reports",
        json={"target_type": "page", "target_handle": "report-page", "reason": "spam"},
    )

    assert profile_report.status_code == 201
    assert page_report.status_code == 201
    assert profile_report.json()["target_type"] == "profile"
    assert "reporter_user_id" not in profile_report.json()
    reports = owner.get("/v1/moderation/reports")
    assert reports.status_code == 200
    assert reports.json() == [
        {
            "id": page_report.json()["id"],
            "status": "open",
            "reason": "spam",
            "target_type": "page",
            "target_id": page_response.json()["id"],
            "target_handle": "report-page",
            "note": None,
            "created_at": page_report.json()["created_at"],
        }
    ]
    assert (
        session.scalar(select(ContentReport).where(ContentReport.id == profile_report.json()["id"]))
        is not None
    )
    audit_entries = session.scalars(
        select(SafetyAuditLog)
        .where(SafetyAuditLog.actor_user_id == reporter_id)
        .order_by(SafetyAuditLog.created_at)
    ).all()
    assert [entry.action for entry in audit_entries] == ["report.created", "report.created"]
    assert {entry.target_type for entry in audit_entries} == {"profile", "page"}
    assert all("email" not in entry.metadata_json for entry in audit_entries)

    audit_response = reporter.get("/v1/safety/audit-log")
    assert audit_response.status_code == 200
    assert [entry["action"] for entry in audit_response.json()] == [
        "report.created",
        "report.created",
    ]
    assert "reporter@example.test" not in str(audit_response.json())


def test_user_block_prevents_notifications_and_internal_check(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    blocker = TestClient(app)
    actor = TestClient(app)
    published: list[dict[str, object]] = []
    monkeypatch.setattr(
        routes,
        "publish_user_block_changed",
        lambda _settings, payload: published.append(payload),
    )
    blocker_register = blocker.post(
        "/v1/auth/register",
        json={"email": "blocker@example.test", "username": "blocker", "password": "StrongPass123!"},
    )
    assert blocker_register.status_code == 201
    actor_register = actor.post(
        "/v1/auth/register",
        json={"email": "blocked@example.test", "username": "blocked", "password": "StrongPass123!"},
    )
    assert actor_register.status_code == 201
    blocker_id = blocker_register.json()["user"]["id"]
    actor_id = actor_register.json()["user"]["id"]

    block_response = blocker.post("/v1/me/blocks", json={"username": "blocked"})
    assert block_response.status_code == 201
    assert published[-1] == {
        "action": "blocked",
        "blocker_user_id": blocker_id,
        "blocker_username": "blocker",
        "blocked_user_id": actor_id,
        "blocked_username": "blocked",
    }
    assert (
        session.scalar(select(UserBlock).where(UserBlock.blocker_user_id == blocker_id)) is not None
    )
    block_audit = session.scalar(
        select(SafetyAuditLog).where(
            SafetyAuditLog.actor_user_id == blocker_id,
            SafetyAuditLog.action == "user.blocked",
        )
    )
    assert block_audit is not None
    assert block_audit.target_type == "user"
    assert block_audit.target_id == actor_id
    assert "token" not in block_audit.metadata_json

    check = actor.get(
        f"/internal/v1/users/{blocker_id}/blocks/{actor_id}",
        headers={"X-Threshold-Internal-Token": "test-internal-token"},
    )
    assert check.status_code == 200
    assert check.json() == {"blocked": True}

    page = Page(slug="blocked-note-page", display_name="Blocked Note Page", page_type="club")
    session.add(page)
    session.flush()
    session.add(PageMembership(page_id=page.id, user_id=actor_id, role=PageMembershipRole.owner))
    session.commit()
    add_member = actor.put("/v1/pages/blocked-note-page/members/blocker", json={"role": "editor"})
    assert add_member.status_code == 200
    assert (
        session.scalars(
            select(NotificationEvent).where(NotificationEvent.user_id == blocker_id)
        ).all()
        == []
    )

    unblock_response = blocker.delete("/v1/me/blocks/blocked")
    assert unblock_response.status_code == 204
    assert published[-1] == {
        "action": "unblocked",
        "blocker_user_id": blocker_id,
        "blocker_username": "blocker",
        "blocked_user_id": actor_id,
        "blocked_username": "blocked",
    }


def test_internal_mention_target_resolves_profiles_and_pages(session: Session) -> None:
    client = TestClient(app)
    registered = client.post(
        "/v1/auth/register",
        json={
            "email": "mention-target@example.test",
            "username": "mentiontarget",
            "password": "StrongPass123!",
            "display_name": "Mention Target",
        },
    )
    assert registered.status_code == 201
    user_id = registered.json()["user"]["id"]
    page = client.post(
        "/v1/pages",
        json={"slug": "mention-page", "display_name": "Mention Page", "page_type": "club"},
    )
    assert page.status_code == 201

    profile = client.get(
        "/internal/v1/mention-targets/profiles/mentiontarget",
        headers={"X-Threshold-Internal-Token": "test-internal-token"},
    )
    page_response = client.get(
        "/internal/v1/mention-targets/pages/mention-page",
        headers={"X-Threshold-Internal-Token": "test-internal-token"},
    )

    assert profile.status_code == 200
    assert profile.json() == {
        "target_type": "user",
        "target_id": user_id,
        "handle": "mentiontarget",
        "display_name": "Mention Target",
        "target_url": "/profiles/mentiontarget",
        "recipient_user_id": user_id,
    }
    assert page_response.status_code == 200
    assert page_response.json() == {
        "target_type": "page",
        "target_id": page.json()["id"],
        "handle": "mention-page",
        "display_name": "Mention Page",
        "target_url": "/pages/mention-page",
        "recipient_user_id": None,
    }


def test_internal_mention_target_missing_profile_returns_404(session: Session) -> None:
    client = TestClient(app)

    response = client.get(
        "/internal/v1/mention-targets/profiles/missing",
        headers={"X-Threshold-Internal-Token": "test-internal-token"},
    )

    assert response.status_code == 404


def test_search_normalizes_handle_prefix_and_exposes_no_private_data(session: Session) -> None:
    client = TestClient(app)
    registered = client.post(
        "/v1/auth/register",
        json={
            "email": "search-target@example.test",
            "username": "searchtarget",
            "password": "StrongPass123!",
            "display_name": "Search Target",
        },
    )
    assert registered.status_code == 201

    response = client.get("/v1/search?q=@searchtarget")

    assert response.status_code == 200
    assert response.json() == [
        {
            "type": "consumer",
            "handle": "searchtarget",
            "display_name": "Search Target",
            "subtitle": None,
        }
    ]


def test_notifications_inbox_internal_create_read_state_and_dedupe(session: Session) -> None:
    client = TestClient(app)
    recipient_client = TestClient(app)
    recipient = recipient_client.post(
        "/v1/auth/register",
        json={
            "email": "notify-recipient@example.test",
            "username": "notifyrecipient",
            "password": "StrongPass123!",
        },
    )
    actor = client.post(
        "/v1/auth/register",
        json={
            "email": "notify-actor@example.test",
            "username": "notifyactor",
            "password": "StrongPass123!",
        },
    )
    assert recipient.status_code == 201
    assert actor.status_code == 201
    recipient_id = recipient.json()["user"]["id"]
    actor_id = actor.json()["user"]["id"]

    payload = {
        "recipient_user_id": recipient_id,
        "actor_user_id": actor_id,
        "type": "comment.created",
        "target_type": "post",
        "target_id": "post-1",
        "target_url": "/posts/post-1",
        "title": "notifyactor commented on your post",
        "body": "factual copy only",
        "dedupe_key": "comment:post-1:notifyactor:notifyrecipient",
        "metadata": {"thread_id": "post-1", "token": "do-not-store"},
    }
    first = client.post(
        "/internal/v1/notifications",
        headers={"X-Threshold-Internal-Token": "test-internal-token"},
        json=payload,
    )
    duplicate = client.post(
        "/internal/v1/notifications",
        headers={"X-Threshold-Internal-Token": "test-internal-token"},
        json=payload,
    )
    assert first.status_code == 201
    assert duplicate.status_code == 200

    inbox = recipient_client.get("/v1/notifications")
    assert inbox.status_code == 200
    notifications = inbox.json()
    assert len(notifications) == 1
    assert notifications[0]["type"] == "comment.created"
    assert notifications[0]["actor_user_id"] == actor_id
    assert notifications[0]["recipient_user_id"] == recipient_id
    assert notifications[0]["read_at"] is None
    assert "token" not in str(notifications[0]["metadata"])

    unread = recipient_client.get("/v1/notifications/unread-count")
    assert unread.status_code == 200
    assert unread.json() == {"count": 1}

    mark = recipient_client.post(f"/v1/notifications/{notifications[0]['id']}/read")
    assert mark.status_code == 200
    assert recipient_client.get("/v1/notifications/unread-count").json() == {"count": 0}


def test_follow_creates_factual_notification_and_respects_blocks(session: Session) -> None:
    follower = TestClient(app)
    target = TestClient(app)
    follower_register = follower.post(
        "/v1/auth/register",
        json={
            "email": "follower-note@example.test",
            "username": "followernote",
            "password": "StrongPass123!",
        },
    )
    target_register = target.post(
        "/v1/auth/register",
        json={
            "email": "target-note@example.test",
            "username": "targetnote",
            "password": "StrongPass123!",
        },
    )
    assert follower_register.status_code == 201
    assert target_register.status_code == 201
    follower_id = follower_register.json()["user"]["id"]
    target_id = target_register.json()["user"]["id"]

    follow = follower.post(
        "/v1/me/follows", json={"target_type": "consumer", "target_handle": "targetnote"}
    )
    assert follow.status_code == 200
    inbox = target.get("/v1/notifications")
    assert [item["type"] for item in inbox.json()] == ["follow.created"]
    assert inbox.json()[0]["actor_user_id"] == follower_id
    assert inbox.json()[0]["target_id"] == target_id
    assert inbox.json()[0]["target_url"] == "/u/followernote"
    assert inbox.json()[0]["metadata"]["actor_username"] == "followernote"
    assert "followed you" in inbox.json()[0]["title"]

    target.post("/v1/me/blocks", json={"username": "followernote"})
    follower.delete("/v1/me/follows/consumer/targetnote")
    blocked_follow = follower.post(
        "/v1/me/follows", json={"target_type": "consumer", "target_handle": "targetnote"}
    )
    assert blocked_follow.status_code == 200
    assert session.scalars(
        select(NotificationEvent).where(NotificationEvent.user_id == target_id)
    ).all()
    assert target.get("/v1/notifications/unread-count").json() == {"count": 1}


def test_notification_preferences_default_and_update(session: Session) -> None:
    client = TestClient(app)
    registered = client.post(
        "/v1/auth/register",
        json={
            "email": "prefs-default@example.test",
            "username": "prefsdefault",
            "password": "StrongPass123!",
        },
    )
    assert registered.status_code == 201
    user_id = registered.json()["user"]["id"]

    default_response = client.get("/v1/notifications/preferences")
    assert default_response.status_code == 200
    assert default_response.json() == {
        "mentions_enabled": True,
        "engagement_enabled": True,
        "event_updates_enabled": True,
        "page_updates_enabled": True,
    }
    assert (
        session.scalar(
            select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        )
        is not None
    )

    update_response = client.put(
        "/v1/notifications/preferences",
        json={"engagement_enabled": False, "page_updates_enabled": False},
    )
    assert update_response.status_code == 200
    assert update_response.json() == {
        "mentions_enabled": True,
        "engagement_enabled": False,
        "event_updates_enabled": True,
        "page_updates_enabled": False,
    }


def test_muted_engagement_suppresses_internal_notification(session: Session) -> None:
    recipient_client = TestClient(app)
    actor_client = TestClient(app)
    recipient = recipient_client.post(
        "/v1/auth/register",
        json={
            "email": "muted-engagement@example.test",
            "username": "mutedengagement",
            "password": "StrongPass123!",
        },
    )
    actor = actor_client.post(
        "/v1/auth/register",
        json={
            "email": "muted-actor@example.test",
            "username": "mutedactor",
            "password": "StrongPass123!",
        },
    )
    assert recipient.status_code == 201
    assert actor.status_code == 201
    recipient_id = recipient.json()["user"]["id"]
    actor_id = actor.json()["user"]["id"]

    prefs = recipient_client.put(
        "/v1/notifications/preferences", json={"engagement_enabled": False}
    )
    assert prefs.status_code == 200

    created = actor_client.post(
        "/internal/v1/notifications",
        headers={"X-Threshold-Internal-Token": "test-internal-token"},
        json={
            "recipient_user_id": recipient_id,
            "actor_user_id": actor_id,
            "type": "comment.created",
            "target_type": "post",
            "target_id": "post-muted",
            "title": "mutedactor commented on your post",
            "metadata": {"thread_id": "post-muted"},
        },
    )
    assert created.status_code == 200
    assert created.json()["id"] == ""
    assert session.scalars(select(NotificationEvent)).all() == []


def test_critical_page_role_notification_bypasses_page_update_mute(session: Session) -> None:
    owner = TestClient(app)
    member = TestClient(app)
    owner_register = owner.post(
        "/v1/auth/register",
        json={
            "email": "critical-owner@example.test",
            "username": "criticalowner",
            "password": "StrongPass123!",
        },
    )
    member_register = member.post(
        "/v1/auth/register",
        json={
            "email": "critical-member@example.test",
            "username": "criticalmember",
            "password": "StrongPass123!",
        },
    )
    assert owner_register.status_code == 201
    assert member_register.status_code == 201
    member_id = member_register.json()["user"]["id"]

    assert member.put(
        "/v1/notifications/preferences", json={"page_updates_enabled": False}
    ).status_code == 200

    page = owner.post(
        "/v1/pages",
        json={"slug": "critical-page", "display_name": "Critical Page", "page_type": "club"},
    )
    assert page.status_code == 201
    add_member = owner.put(
        "/v1/pages/critical-page/members/criticalmember", json={"role": "editor"}
    )
    assert add_member.status_code == 200

    rows = session.scalars(
        select(NotificationEvent).where(NotificationEvent.user_id == member_id)
    ).all()
    assert [row.event_type for row in rows] == ["page.member_upserted"]
    assert rows[0].target_url == "/pages/critical-page"
    assert rows[0].payload["page_slug"] == "critical-page"
    assert rows[0].payload["page_name"] == "Critical Page"
    assert rows[0].payload["role"] == "editor"


def test_repeated_no_dedupe_notification_collapses_by_default_key(session: Session) -> None:
    recipient_client = TestClient(app)
    actor_client = TestClient(app)
    recipient = recipient_client.post(
        "/v1/auth/register",
        json={
            "email": "fallback-dedupe-recipient@example.test",
            "username": "fallbackrecipient",
            "password": "StrongPass123!",
        },
    )
    actor = actor_client.post(
        "/v1/auth/register",
        json={
            "email": "fallback-dedupe-actor@example.test",
            "username": "fallbackactor",
            "password": "StrongPass123!",
        },
    )
    assert recipient.status_code == 201
    assert actor.status_code == 201
    payload = {
        "recipient_user_id": recipient.json()["user"]["id"],
        "actor_user_id": actor.json()["user"]["id"],
        "type": "reaction.created",
        "target_type": "post",
        "target_id": "post-dedupe",
        "title": "fallbackactor reacted to your post",
    }

    first = actor_client.post(
        "/internal/v1/notifications",
        headers={"X-Threshold-Internal-Token": "test-internal-token"},
        json=payload,
    )
    second = actor_client.post(
        "/internal/v1/notifications",
        headers={"X-Threshold-Internal-Token": "test-internal-token"},
        json=payload,
    )

    assert first.status_code == 201
    assert second.status_code == 200
    rows = session.scalars(select(NotificationEvent)).all()
    assert len(rows) == 1
    assert rows[0].dedupe_key == (
        f"reaction.created:post:post-dedupe:{payload['actor_user_id']}:{payload['recipient_user_id']}"
    )
