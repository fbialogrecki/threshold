from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy import select
from sqlalchemy.orm import Session
from users.account_erasure import run_account_erasure_jobs
from users.domain.models import (
    ApplicationUser,
    AuthAuditLog,
    ContentReport,
    EmailVerificationToken,
    Follow,
    NotificationEvent,
    NotificationPreference,
    Page,
    PageMembership,
    PageMembershipRole,
    PageResidency,
    PasswordResetToken,
    SafetyAuditLog,
    SecretLocationKeyEnvelope,
    SecretLocationPayload,
    UserSession,
)
from users.main import app

from users import main_dependencies


def _get_authenticated_client(
    session: Session, email: str, username: str
) -> tuple[TestClient, str]:
    client = TestClient(app)
    response = client.post(
        "/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": "StrongPass123!",
            "display_name": username.capitalize(),
        },
    )
    assert response.status_code == 201
    user_id = response.json()["user"]["id"]
    return client, user_id


def test_put_me_onboarding(session: Session) -> None:
    client, user_id = _get_authenticated_client(session, "onb@example.test", "onbuser")

    # Update onboarding preferences
    response = client.put(
        "/v1/me/onboarding",
        json={
            "city": "Berlin",
            "preferred_scenes": "Techno",
            "onboarding_skipped": True,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["onboarding_preferences"]["city"] == "Berlin"
    assert body["onboarding_preferences"]["preferred_scenes"] == "Techno"
    assert body["onboarding_preferences"]["onboarding_skipped"] is False

    # Verify directly in DB
    user = session.get(ApplicationUser, user_id)
    assert user is not None
    assert user.onboarding_preferences is not None
    assert user.onboarding_preferences.city == "Berlin"
    assert user.onboarding_preferences.preferred_scenes == "Techno"


def test_internal_profile_routes_require_internal_token(session: Session) -> None:
    client, user_id = _get_authenticated_client(
        session, "internal-profile@example.test", "internalprofile"
    )
    profile_payload = {
        "authentik_subject": "authentik|internal-profile",
        "email": "internal-profile-sso@example.test",
        "username": "internalprofilesso",
    }
    onboarding_payload = {"city": "Berlin", "preferred_scenes": "Techno"}

    missing_profile = client.post("/internal/v1/current-profile", json=profile_payload)
    assert missing_profile.status_code == 401

    allowed_profile = client.post(
        "/internal/v1/current-profile",
        headers={"X-Threshold-Internal-Token": "test-internal-token"},
        json=profile_payload,
    )
    assert allowed_profile.status_code == 200

    missing_onboarding = client.put(
        f"/internal/v1/users/{user_id}/onboarding-preferences",
        json=onboarding_payload,
    )
    assert missing_onboarding.status_code == 401

    allowed_onboarding = client.put(
        f"/internal/v1/users/{user_id}/onboarding-preferences",
        headers={"X-Threshold-Internal-Token": "test-internal-token"},
        json=onboarding_payload,
    )
    assert allowed_onboarding.status_code == 200
    assert allowed_onboarding.json()["onboarding_preferences"]["city"] == "Berlin"


def test_patch_me_profile_success(session: Session) -> None:
    client, user_id = _get_authenticated_client(session, "prof@example.test", "profuser")

    response = client.patch(
        "/v1/me/profile",
        json={
            "display_name": "Updated Name",
            "bio": "New Bio",
            "city": "Paris",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["consumer_profile"]["display_name"] == "Updated Name"
    assert body["consumer_profile"]["bio"] == "New Bio"
    assert body["onboarding_preferences"]["city"] == "Paris"


def test_patch_me_profile_username_taken(session: Session) -> None:
    client1, user1_id = _get_authenticated_client(session, "user1@example.test", "user1")
    client2, user2_id = _get_authenticated_client(session, "user2@example.test", "user2")

    # Try updating user2 username to user1
    response = client2.patch(
        "/v1/me/profile",
        json={"username": "user1"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "username already taken"

    # Updating to same username should succeed (idempotency / ignored if same user)
    response = client2.patch(
        "/v1/me/profile",
        json={"username": "user2"},
    )
    assert response.status_code == 200


def test_post_me_artist_success(session: Session) -> None:
    client, user_id = _get_authenticated_client(session, "art@example.test", "artuser")

    response = client.post(
        "/v1/me/artist",
        json={
            "role": "DJ / Producer",
            "location": "London",
            "links": [{"label": "SoundCloud", "url": "https://soundcloud.com/artuser"}],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["artist_profile"] is not None
    assert body["artist_profile"]["role"] == "DJ / Producer"
    assert body["artist_profile"]["location"] == "London"
    assert body["artist_profile"]["links"] == [
        {"label": "SoundCloud", "url": "https://soundcloud.com/artuser"}
    ]


def test_post_me_artist_invalid_links(session: Session) -> None:
    client, user_id = _get_authenticated_client(session, "art_bad@example.test", "artbad")

    response = client.post(
        "/v1/me/artist",
        json={
            "role": "DJ",
            "location": "London",
            "links": [{"label": "SoundCloud", "url": "ftp://soundcloud.com/artuser"}],
        },
    )
    assert response.status_code == 422


def test_delete_me_gdpr(session: Session, monkeypatch: MonkeyPatch) -> None:
    client, user_id = _get_authenticated_client(session, "delete@example.test", "deleteuser")
    _, other_user_id = _get_authenticated_client(session, "other@example.test", "otheruser")
    erasure_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "users.account_erasure.anonymize_social_author",
        lambda _settings, called_user_id: erasure_calls.append(("social", called_user_id)),
    )
    monkeypatch.setattr(
        "users.account_erasure.erase_events_account",
        lambda _settings, called_user_id, _artist_profile_ids: erasure_calls.append(
            ("events", called_user_id)
        ),
    )
    monkeypatch.setattr(
        "users.account_erasure.erase_media_assets",
        lambda _settings, called_user_id: erasure_calls.append(("media", called_user_id)),
    )

    # Add artist profile & preferences to check they aren't completely broken
    client.post(
        "/v1/me/artist",
        json={
            "role": "Live Act",
            "location": "Berlin",
            "links": [],
        },
    )
    client.put("/v1/me/onboarding", json={"city": "Berlin", "preferred_scenes": "Techno"})
    client.post("/v1/auth/password/reset/request", json={"email": "delete@example.test"})
    notification_from_deleted = NotificationEvent(
        user_id=other_user_id,
        actor_user_id=user_id,
        event_type="follow.created",
        target_type="user",
        target_id=user_id,
        title="Delete User followed you",
    )
    target_follow = Follow(
        follower_user_id=other_user_id,
        target_type="consumer",
        target_id=user_id,
        target_handle="deleteuser",
    )
    legacy_handle_follow = Follow(
        follower_user_id=other_user_id,
        target_type="consumer",
        target_id="legacy-target-id",
        target_handle="deleteuser",
    )
    report = ContentReport(
        reporter_user_id=user_id,
        target_type="profile",
        target_id=user_id,
        target_handle="deleteuser",
        reason="test",
    )
    audit = SafetyAuditLog(
        actor_user_id=user_id,
        action="report.created",
        target_type="profile",
        target_id=user_id,
        metadata_json={"user_id": user_id, "username": "deleteuser"},
    )
    auth_audit = AuthAuditLog(
        user_id=user_id,
        event_type="security.retained",
        result="success",
        subject_hash="subject-hash",
        ip_hash="ip-hash",
        user_agent_hash="ua-hash",
        request_id="request-id",
        metadata_json={"user_id": user_id},
    )
    page = Page(
        slug="erasure-page",
        display_name="Erasure Page",
        avatar_media_asset_id="avatar-asset",
        avatar_media_owner_user_id=user_id,
    )
    secret_payload = SecretLocationPayload(
        event_id="event-erasure",
        city="Berlin",
        encrypted_payload_ciphertext="ciphertext",
        encrypted_payload_nonce="nonce",
        crypto_suite="test-suite",
    )
    session.add_all(
        [
            NotificationEvent(
                user_id=user_id,
                event_type="follow.created",
                target_type="user",
                target_id="actor-1",
                title="Someone followed you",
            ),
            notification_from_deleted,
            target_follow,
            legacy_handle_follow,
            report,
            audit,
            auth_audit,
            NotificationPreference(user_id=user_id),
            page,
            secret_payload,
        ]
    )
    session.flush()
    membership = PageMembership(
        page_id=page.id,
        user_id=user_id,
        role=PageMembershipRole.owner,
    )
    residency = PageResidency(
        page_id=page.id,
        artist_user_id=user_id,
        invited_by_user_id=other_user_id,
    )
    invited_residency = PageResidency(
        page_id=page.id,
        artist_user_id=other_user_id,
        invited_by_user_id=user_id,
    )
    envelope = SecretLocationKeyEnvelope(
        payload_id=secret_payload.id,
        recipient_user_id=user_id,
        encrypted_payload_key="encrypted-key",
    )
    session.add_all([membership, residency, invited_residency, envelope])
    session.commit()
    notification_from_deleted_id = notification_from_deleted.id
    target_follow_id = target_follow.id
    legacy_handle_follow_id = legacy_handle_follow.id
    report_id = report.id
    audit_id = audit.id
    auth_audit_id = auth_audit.id
    page_id = page.id
    membership_id = membership.id
    residency_id = residency.id
    invited_residency_id = invited_residency.id
    envelope_id = envelope.id

    # Perform DELETE /v1/me
    response = client.delete("/v1/me")
    assert response.status_code == 202
    assert run_account_erasure_jobs(main_dependencies.session_factory, max_jobs=1) == 1

    # Verify the cookies are cleared/deleted
    # Standard FastAPI TestClient keeps cookies unless cleared or response deleted them
    # But let's check what the DB shows
    session.expire_all()
    user = session.get(ApplicationUser, user_id)
    assert user is not None
    assert user.status == "deleted"
    assert user.deleted_at is not None
    assert user.email is None
    assert user.email_normalized is None
    assert user.email_verified_at is None
    assert user.username is None
    assert user.username_normalized is None
    assert user.authentik_subject is None
    assert user.credential is None
    assert user.consumer_profile is not None
    assert user.consumer_profile.display_name == "Deleted User"
    assert user.consumer_profile.bio is None
    assert user.consumer_profile.avatar_media_asset_id is None
    assert user.artist_profile is None
    assert user.onboarding_preferences is None
    assert session.scalars(
        select(EmailVerificationToken).where(EmailVerificationToken.user_id == user_id)
    ).all() == []
    assert session.scalars(
        select(PasswordResetToken).where(PasswordResetToken.user_id == user_id)
    ).all() == []
    assert (
        session.scalars(select(NotificationEvent).where(NotificationEvent.user_id == user_id)).all()
        == []
    )
    assert session.get(NotificationEvent, notification_from_deleted_id) is None
    assert session.get(Follow, target_follow_id) is None
    assert session.get(Follow, legacy_handle_follow_id) is None
    scrubbed_report = session.get(ContentReport, report_id)
    scrubbed_audit = session.get(SafetyAuditLog, audit_id)
    assert scrubbed_report is not None
    assert scrubbed_report.reporter_user_id is None
    assert scrubbed_report.target_id == "deleted-user"
    assert scrubbed_report.target_handle == "deleted-user"
    assert scrubbed_audit is not None
    assert scrubbed_audit.actor_user_id is None
    assert scrubbed_audit.target_id == "deleted-user"
    assert scrubbed_audit.metadata_json == {"user_id": None, "username": None}
    retained_auth_audit = session.get(AuthAuditLog, auth_audit_id)
    assert retained_auth_audit is not None
    assert retained_auth_audit.user_id is None
    assert retained_auth_audit.subject_hash is None
    assert retained_auth_audit.ip_hash is None
    assert retained_auth_audit.user_agent_hash is None
    assert retained_auth_audit.request_id is None
    assert retained_auth_audit.metadata_json == {"user_id": None}
    assert session.get(PageMembership, membership_id) is None
    assert session.get(PageResidency, residency_id) is None
    assert session.get(PageResidency, invited_residency_id) is None
    assert session.get(SecretLocationKeyEnvelope, envelope_id) is None
    retained_page = session.get(Page, page_id)
    assert retained_page is not None
    assert retained_page.avatar_media_asset_id is None
    assert retained_page.avatar_media_owner_user_id is None
    assert session.scalar(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    ) is None

    # Session tokens and linked IP/UA hashes are deleted immediately.
    sessions = session.scalars(select(UserSession).where(UserSession.user_id == user_id)).all()
    assert sessions == []
    assert erasure_calls == [
        ("social", user_id),
        ("events", user_id),
        ("media", user_id),
    ]

    # Try GET /v1/auth/me should return 401
    get_me = client.get("/v1/auth/me")
    assert get_me.status_code == 401



def test_follow_and_unfollow_endpoints(session: Session) -> None:
    # Set up some users & pages in the DB
    follower_client, follower_id = _get_authenticated_client(
        session, "follower@example.test", "follower"
    )
    artist_client, artist_id = _get_authenticated_client(
        session, "artist_target@example.test", "artisttarget"
    )
    consumer_client, consumer_id = _get_authenticated_client(
        session, "consumer_target@example.test", "consumertarget"
    )

    # Make artist_target an actual artist
    artist_client.post(
        "/v1/me/artist",
        json={"role": "DJ", "location": "Madrid", "links": []},
    )

    # Create club & collective pages
    club_page = Page(slug="club-x", display_name="Club X", page_type="club", city="Berlin")
    collective_page = Page(
        slug="col-y", display_name="Collective Y", page_type="collective", city="London"
    )
    session.add_all([club_page, collective_page])
    session.commit()

    # 1. Follow consumer target
    response = follower_client.post(
        "/v1/me/follows",
        json={"target_type": "consumer", "target_handle": "consumertarget"},
    )
    assert response.status_code == 200

    # 2. Follow artist target
    response = follower_client.post(
        "/v1/me/follows",
        json={"target_type": "artist", "target_handle": "artisttarget"},
    )
    assert response.status_code == 200

    # 3. Follow club page
    response = follower_client.post(
        "/v1/me/follows",
        json={"target_type": "club", "target_handle": "club-x"},
    )
    assert response.status_code == 200

    # 4. Follow collective page
    response = follower_client.post(
        "/v1/me/follows",
        json={"target_type": "collective", "target_handle": "col-y"},
    )
    assert response.status_code == 200

    # 5. Idempotency check: Follow same consumer again
    response = follower_client.post(
        "/v1/me/follows",
        json={"target_type": "consumer", "target_handle": "consumertarget"},
    )
    assert response.status_code == 200

    # 6. Invalid target follow returns 404
    response = follower_client.post(
        "/v1/me/follows",
        json={"target_type": "consumer", "target_handle": "nonexistent"},
    )
    assert response.status_code == 404

    # 7. GET /v1/me/follows lists everything
    response = follower_client.get("/v1/me/follows")
    assert response.status_code == 200
    follows = response.json()
    assert len(follows) == 4

    # Check structure & display name resolution
    assert {
        (f["target_type"], f["target_handle"], f["display_name"]) for f in follows
    } == {
        ("consumer", "consumertarget", "Consumertarget"),
        ("artist", "artisttarget", "Artisttarget"),
        ("page", "club-x", "Club X"),
        ("page", "col-y", "Collective Y"),
    }

    # 8. Unfollow consumer (case insensitive check)
    response = follower_client.delete("/v1/me/follows/consumer/CONSUMERtarget")
    assert response.status_code == 204

    # 9. GET /v1/me/follows after unfollow
    response = follower_client.get("/v1/me/follows")
    assert response.status_code == 200
    follows_after = response.json()
    assert len(follows_after) == 3
    assert not any(f["target_type"] == "consumer" for f in follows_after)


def test_generic_page_follow_supports_all_page_types(session: Session) -> None:
    client, _ = _get_authenticated_client(
        session, "page-follower@example.test", "pagefollower"
    )
    pages = [
        Page(
            slug=f"{page_type}-follow",
            display_name=f"{page_type.title()} Follow",
            page_type=page_type,
            city="Warsaw",
        )
        for page_type in ("club", "collective", "project", "festival")
    ]
    session.add_all(pages)
    session.commit()

    for page in pages:
        response = client.post(
            "/v1/me/follows",
            json={"target_type": "page", "target_handle": page.slug},
        )
        assert response.status_code == 200

    follows = client.get("/v1/me/follows")
    assert follows.status_code == 200
    assert {
        (follow["target_type"], follow["target_handle"])
        for follow in follows.json()
    } == {("page", page.slug) for page in pages}

    unfollow = client.delete("/v1/me/follows/page/project-follow")
    assert unfollow.status_code == 204


def test_page_follow_aliases_dedupe_count_and_unfollow(session: Session) -> None:
    generic_client, generic_id = _get_authenticated_client(
        session, "generic-page-follow@example.test", "genericpagefollow"
    )
    legacy_client, legacy_id = _get_authenticated_client(
        session, "legacy-page-follow@example.test", "legacypagefollow"
    )
    page = Page(
        slug="mixed-page-follow",
        display_name="Mixed Page Follow",
        page_type="festival",
        city="Warsaw",
    )
    session.add(page)
    session.commit()

    assert generic_client.post(
        "/v1/me/follows",
        json={"target_type": "page", "target_handle": page.slug},
    ).status_code == 200
    assert generic_client.post(
        "/v1/me/follows",
        json={"target_type": "club", "target_handle": page.slug},
    ).status_code == 200
    generic_rows = session.scalars(
        select(Follow).where(
            Follow.follower_user_id == generic_id,
            Follow.target_id == page.id,
        )
    ).all()
    assert [(row.target_type, row.target_handle) for row in generic_rows] == [
        ("page", page.slug)
    ]

    assert legacy_client.post(
        "/v1/me/follows",
        json={"target_type": "festival", "target_handle": page.slug},
    ).status_code == 200
    assert legacy_client.post(
        "/v1/me/follows",
        json={"target_type": "page", "target_handle": page.slug},
    ).status_code == 200
    legacy_rows = session.scalars(
        select(Follow).where(
            Follow.follower_user_id == legacy_id,
            Follow.target_id == page.id,
        )
    ).all()
    assert [row.target_type for row in legacy_rows] == ["page"]

    session.add_all(
        [
            Follow(
                follower_user_id=generic_id,
                target_type=target_type,
                target_id=page.id,
                target_handle=page.slug,
            )
            for target_type in ("club", "collective", "project", "festival")
        ]
    )
    session.commit()

    public = generic_client.get(f"/v1/pages/{page.slug}")
    assert public.status_code == 200
    assert public.json()["follower_count"] == 2
    assert public.json()["is_following"] is True

    listed = generic_client.get("/v1/me/follows")
    assert listed.status_code == 200
    assert [
        (follow["target_type"], follow["target_handle"]) for follow in listed.json()
    ] == [("page", page.slug)]

    removed = generic_client.delete(f"/v1/me/follows/collective/{page.slug}")
    assert removed.status_code == 204
    assert session.scalars(
        select(Follow).where(
            Follow.follower_user_id == generic_id,
            Follow.target_id == page.id,
        )
    ).all() == []

    after = generic_client.get(f"/v1/pages/{page.slug}")
    assert after.json()["follower_count"] == 1
    assert after.json()["is_following"] is False
