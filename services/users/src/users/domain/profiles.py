from sqlalchemy import select
from sqlalchemy.orm import Session
from users.domain.models import (
    ApplicationUser,
    ConsumerProfile,
    IdentitySource,
    OnboardingPreferences,
)


def normalize_email(email: str | None) -> str | None:
    return email.strip().lower() if email else None


def normalize_username(username: str | None) -> str | None:
    return username.strip().lower() if username else None


def get_or_create_current_profile(
    session: Session,
    *,
    authentik_subject: str,
    email: str | None,
    username: str | None,
) -> ApplicationUser:
    user = session.scalar(
        select(ApplicationUser).where(ApplicationUser.authentik_subject == authentik_subject)
    )
    if user is None:
        user = ApplicationUser(
            authentik_subject=authentik_subject,
            email=email,
            email_normalized=normalize_email(email),
            username=username,
            username_normalized=normalize_username(username),
            identity_source=IdentitySource.authentik_internal.value,
            consumer_profile=ConsumerProfile(display_name=username or email),
            onboarding_preferences=OnboardingPreferences(),
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    changed = False
    if user.consumer_profile is None:
        user.consumer_profile = ConsumerProfile(display_name=username or email)
        changed = True
    if user.onboarding_preferences is None:
        user.onboarding_preferences = OnboardingPreferences()
        changed = True
    if email is not None and user.email != email:
        user.email = email
        user.email_normalized = normalize_email(email)
        changed = True
    if username is not None and user.username != username:
        user.username = username
        user.username_normalized = normalize_username(username)
        changed = True
    if not user.identity_source:
        user.identity_source = IdentitySource.authentik_internal.value
        changed = True
    if changed:
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


def update_onboarding_preferences(
    session: Session,
    *,
    user_id: str,
    city: str | None,
    preferred_scenes: str | None,
    onboarding_skipped: bool = False,
) -> OnboardingPreferences:
    preferences = session.scalar(
        select(OnboardingPreferences).where(OnboardingPreferences.user_id == user_id)
    )
    if preferences is None:
        preferences = OnboardingPreferences(user_id=user_id)
    preferences.city = city
    preferences.preferred_scenes = preferred_scenes
    preferences.onboarding_skipped = onboarding_skipped
    session.add(preferences)
    session.commit()
    session.refresh(preferences)
    return preferences
