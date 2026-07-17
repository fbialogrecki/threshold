from sqlalchemy.orm import Session
from users.domain.models import ApplicationUser
from users.domain.profiles import get_or_create_current_profile, update_onboarding_preferences


def test_current_profile_is_created_once(session: Session) -> None:
    first = get_or_create_current_profile(
        session,
        authentik_subject="ak-user-1",
        email="user@example.test",
        username="user1",
    )
    second = get_or_create_current_profile(
        session,
        authentik_subject="ak-user-1",
        email="updated@example.test",
        username="user-one",
    )

    assert second.id == first.id
    assert second.email == "updated@example.test"
    assert second.username == "user-one"
    assert second.consumer_profile is not None
    assert second.consumer_profile.display_name == "user1"
    assert second.onboarding_preferences is not None


def test_current_profile_repairs_missing_related_rows(session: Session) -> None:
    user = ApplicationUser(authentik_subject="ak-user-orphan", email=None, username="orphan")
    session.add(user)
    session.commit()

    repaired = get_or_create_current_profile(
        session,
        authentik_subject="ak-user-orphan",
        email=None,
        username="orphan",
    )

    assert repaired.consumer_profile is not None
    assert repaired.onboarding_preferences is not None


def test_onboarding_preferences_can_be_updated(session: Session) -> None:
    user = get_or_create_current_profile(
        session,
        authentik_subject="ak-user-2",
        email=None,
        username="user2",
    )

    preferences = update_onboarding_preferences(
        session,
        user_id=user.id,
        city="Warsaw",
        preferred_scenes="techno,ambient",
    )

    assert preferences.city == "Warsaw"
    assert preferences.preferred_scenes == "techno,ambient"
