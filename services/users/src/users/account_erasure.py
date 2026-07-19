import asyncio
import logging
from contextlib import suppress
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import delete, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from users.domain.models import (
    AccountErasureJob,
    ApplicationUser,
    AuthAuditLog,
    ContentReport,
    EmailVerificationToken,
    Follow,
    NotificationEvent,
    NotificationPreference,
    Page,
    PageMembership,
    PageResidency,
    PasswordResetToken,
    SafetyAuditLog,
    SecretLocationKeyEnvelope,
    UserBlock,
    UserSession,
    utc_now,
)
from users.events_client import erase_events_account
from users.media_client import erase_media_assets
from users.settings import Settings
from users.social_client import anonymize_social_author

logger = logging.getLogger(__name__)

_NEXT_STAGE = {"social": "events", "events": "media", "media": "local"}


def enqueue_account_erasure(session: Session, user: ApplicationUser) -> AccountErasureJob:
    """Fence the account and durably enqueue erasure in one database transaction."""
    existing = session.scalar(
        select(AccountErasureJob).where(AccountErasureJob.user_id == user.id)
    )
    if existing is not None:
        return existing

    now = utc_now()
    user.status = "erasure_pending"
    session.execute(delete(UserSession).where(UserSession.user_id == user.id))
    session.execute(
        delete(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
    )
    session.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
    job = AccountErasureJob(user_id=user.id, next_attempt_at=now)
    session.add_all([user, job])
    try:
        session.commit()
    except IntegrityError:
        # A concurrent request won the unique user_id race. Its transaction is the
        # durable source of truth and already applied the account fence.
        session.rollback()
        existing = session.scalar(
            select(AccountErasureJob).where(AccountErasureJob.user_id == user.id)
        )
        if existing is None:
            raise
        return existing
    return job


def _claim_next_job(
    factory: sessionmaker[Session], *, now: datetime, lease_seconds: int
) -> tuple[str, str] | None:
    owner = str(uuid4())
    with factory() as session:
        statement = (
            select(AccountErasureJob)
            .where(
                AccountErasureJob.completed_at.is_(None),
                AccountErasureJob.next_attempt_at <= now,
                or_(
                    AccountErasureJob.lease_expires_at.is_(None),
                    AccountErasureJob.lease_expires_at <= now,
                ),
            )
            .order_by(AccountErasureJob.created_at, AccountErasureJob.id)
            .limit(1)
        )
        if session.bind is not None and session.bind.dialect.name == "postgresql":
            statement = statement.with_for_update(skip_locked=True)
        job = session.scalar(statement)
        if job is None:
            return None
        job.lease_owner = owner
        job.lease_expires_at = now + timedelta(seconds=lease_seconds)
        session.commit()
        return job.id, owner


def _scrub_metadata(
    metadata: dict[str, str | int | bool | None], identifiers: set[str]
) -> dict[str, str | int | bool | None]:
    return {
        key: None if isinstance(value, str) and value in identifiers else value
        for key, value in metadata.items()
    }


def _erase_local_data(session: Session, *, user_id: str, now: datetime) -> None:
    user = session.get(ApplicationUser, user_id)
    if user is None:
        return
    deleted_username = user.username
    identifiers = {user_id}
    if deleted_username:
        identifiers.add(deleted_username)

    session.execute(delete(UserSession).where(UserSession.user_id == user_id))
    session.execute(delete(EmailVerificationToken).where(EmailVerificationToken.user_id == user_id))
    session.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user_id))
    session.execute(delete(NotificationPreference).where(NotificationPreference.user_id == user_id))
    session.execute(
        delete(NotificationEvent).where(
            (NotificationEvent.user_id == user_id) | (NotificationEvent.actor_user_id == user_id)
        )
    )
    session.execute(
        delete(UserBlock).where(
            (UserBlock.blocker_user_id == user_id) | (UserBlock.blocked_user_id == user_id)
        )
    )
    follow_predicate = (Follow.follower_user_id == user_id) | (Follow.target_id == user_id)
    if deleted_username:
        follow_predicate |= Follow.target_handle == deleted_username
    session.execute(delete(Follow).where(follow_predicate))
    session.execute(delete(PageMembership).where(PageMembership.user_id == user_id))
    session.execute(
        delete(PageResidency).where(
            (PageResidency.artist_user_id == user_id)
            | (PageResidency.invited_by_user_id == user_id)
        )
    )
    session.execute(
        delete(SecretLocationKeyEnvelope).where(
            SecretLocationKeyEnvelope.recipient_user_id == user_id
        )
    )
    session.execute(
        update(Page)
        .where(Page.avatar_media_owner_user_id == user_id)
        .values(avatar_media_asset_id=None, avatar_media_owner_user_id=None)
    )

    for report in session.scalars(
        select(ContentReport).where(
            (ContentReport.reporter_user_id == user_id) | (ContentReport.target_id == user_id)
        )
    ):
        if report.reporter_user_id == user_id:
            report.reporter_user_id = None
        if report.target_id == user_id:
            report.target_id = "deleted-user"
            report.target_handle = "deleted-user"
    for audit_log in session.scalars(
        select(SafetyAuditLog).where(
            (SafetyAuditLog.actor_user_id == user_id) | (SafetyAuditLog.target_id == user_id)
        )
    ):
        if audit_log.actor_user_id == user_id:
            audit_log.actor_user_id = None
        if audit_log.target_id == user_id:
            audit_log.target_id = "deleted-user"
        audit_log.metadata_json = _scrub_metadata(audit_log.metadata_json, identifiers)
    for auth_log in session.scalars(
        select(AuthAuditLog).where(AuthAuditLog.user_id == user_id)
    ):
        # Security events are retained, but no stable account/network/device
        # identifiers remain attached to them after erasure.
        auth_log.user_id = None
        auth_log.subject_hash = None
        auth_log.ip_hash = None
        auth_log.user_agent_hash = None
        auth_log.request_id = None
        auth_log.metadata_json = _scrub_metadata(auth_log.metadata_json, identifiers)

    user.status = "deleted"
    user.deleted_at = now
    user.credential = None
    user.email = None
    user.email_normalized = None
    user.email_verified_at = None
    user.username = None
    user.username_normalized = None
    user.authentik_subject = None
    if user.consumer_profile is not None:
        user.consumer_profile.display_name = "Deleted User"
        user.consumer_profile.bio = None
        user.consumer_profile.avatar_media_asset_id = None
    user.artist_profile = None
    user.onboarding_preferences = None
    session.add(user)


def _finish_stage(
    factory: sessionmaker[Session], *, job_id: str, owner: str, stage: str, now: datetime
) -> bool:
    with factory() as session:
        job = session.scalar(
            select(AccountErasureJob).where(
                AccountErasureJob.id == job_id,
                AccountErasureJob.lease_owner == owner,
            )
        )
        if job is None or job.current_stage != stage:
            return False
        if stage == "local":
            _erase_local_data(session, user_id=job.user_id, now=now)
            job.current_stage = "completed"
            job.completed_at = now
            job.lease_owner = None
            job.lease_expires_at = None
        else:
            job.current_stage = _NEXT_STAGE[stage]
        job.last_error = None
        session.commit()
        return True


def _record_failure(
    factory: sessionmaker[Session], *, job_id: str, owner: str, exc: Exception, now: datetime
) -> None:
    with factory() as session:
        job = session.scalar(
            select(AccountErasureJob).where(
                AccountErasureJob.id == job_id,
                AccountErasureJob.lease_owner == owner,
            )
        )
        if job is None:
            return
        job.attempt_count += 1
        retry_seconds = min(3600, 2 ** min(job.attempt_count, 10))
        job.next_attempt_at = now + timedelta(seconds=retry_seconds)
        job.last_error = type(exc).__name__[:120]
        job.lease_owner = None
        job.lease_expires_at = None
        session.commit()


def _process_claimed_job(
    factory: sessionmaker[Session], settings: Settings, *, job_id: str, owner: str, now: datetime
) -> None:
    while True:
        with factory() as session:
            job = session.scalar(
                select(AccountErasureJob).where(
                    AccountErasureJob.id == job_id,
                    AccountErasureJob.lease_owner == owner,
                )
            )
            if job is None or job.completed_at is not None:
                return
            stage = job.current_stage
            user_id = job.user_id
            user = session.get(ApplicationUser, user_id)
            artist_profile_ids = (
                [user.artist_profile.id]
                if user is not None and user.artist_profile is not None
                else []
            )
        try:
            if stage == "social":
                anonymize_social_author(settings, user_id)
            elif stage == "events":
                erase_events_account(settings, user_id, artist_profile_ids)
            elif stage == "media":
                erase_media_assets(settings, user_id)
            elif stage != "local":
                raise RuntimeError("invalid account erasure stage")
            if not _finish_stage(factory, job_id=job_id, owner=owner, stage=stage, now=now):
                return
            if stage == "local":
                return
        except Exception as exc:
            logger.exception("account erasure stage failed stage=%s", stage)
            _record_failure(factory, job_id=job_id, owner=owner, exc=exc, now=now)
            return


def run_account_erasure_jobs(
    factory: sessionmaker[Session],
    *,
    settings: Settings | None = None,
    max_jobs: int = 10,
    now: datetime | None = None,
) -> int:
    run_at = now or utc_now()
    worker_settings = settings or Settings()
    processed = 0
    for _ in range(max_jobs):
        claim = _claim_next_job(
            factory,
            now=run_at,
            lease_seconds=worker_settings.account_erasure_lease_seconds,
        )
        if claim is None:
            break
        _process_claimed_job(
            factory,
            worker_settings,
            job_id=claim[0],
            owner=claim[1],
            now=run_at,
        )
        processed += 1
    return processed


async def account_erasure_worker(
    factory: sessionmaker[Session], settings: Settings, stop: asyncio.Event
) -> None:
    while not stop.is_set():
        try:
            await asyncio.to_thread(run_account_erasure_jobs, factory, settings=settings)
        except Exception:
            logger.exception("account erasure worker pass failed")
        with suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=settings.account_erasure_poll_seconds)