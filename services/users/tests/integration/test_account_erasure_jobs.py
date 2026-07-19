import asyncio
from datetime import timedelta

from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy import select
from sqlalchemy.orm import Session
from users.account_erasure import account_erasure_worker, run_account_erasure_jobs
from users.domain.models import AccountErasureJob, ApplicationUser, UserSession, utc_now
from users.main import app

from users import main_dependencies


def _register() -> tuple[TestClient, str]:
    client = TestClient(app)
    response = client.post(
        "/v1/auth/register",
        json={
            "email": "erase-job@example.test",
            "username": "erasejob",
            "password": "StrongPass123!",
            "display_name": "Erase Job",
        },
    )
    assert response.status_code == 201
    return client, response.json()["user"]["id"]


def test_delete_me_persists_job_and_immediately_fences_account(session: Session) -> None:
    client, user_id = _register()

    response = client.delete("/v1/me")

    assert response.status_code == 202
    session.expire_all()
    user = session.get(ApplicationUser, user_id)
    assert user is not None
    assert user.status == "erasure_pending"
    job = session.scalar(select(AccountErasureJob).where(AccountErasureJob.user_id == user_id))
    assert job is not None
    assert job.current_stage == "social"
    assert session.scalars(select(UserSession).where(UserSession.user_id == user_id)).all() == []
    assert client.get("/v1/auth/me").status_code == 401
    assert (
        client.post(
            "/v1/auth/login",
            json={"email_or_username": "erasejob", "password": "StrongPass123!"},
        ).status_code
        == 401
    )


def test_erasure_job_retries_from_checkpoint_after_restart_and_is_idempotent(
    session: Session,
    monkeypatch: MonkeyPatch,
) -> None:
    client, user_id = _register()
    assert client.delete("/v1/me").status_code == 202
    calls: list[str] = []
    events_available = False

    def social(_settings: object, _user_id: str) -> None:
        calls.append("social")

    def events(
        _settings: object, _user_id: str, _artist_profile_ids: list[str]
    ) -> None:
        calls.append("events")
        if not events_available:
            raise RuntimeError("temporary failure")

    def media(_settings: object, _user_id: str) -> None:
        calls.append("media")

    monkeypatch.setattr("users.account_erasure.anonymize_social_author", social)
    monkeypatch.setattr("users.account_erasure.erase_events_account", events)
    monkeypatch.setattr("users.account_erasure.erase_media_assets", media)

    assert run_account_erasure_jobs(main_dependencies.session_factory, max_jobs=1) == 1
    session.expire_all()
    job = session.scalar(select(AccountErasureJob).where(AccountErasureJob.user_id == user_id))
    assert job is not None
    assert job.current_stage == "events"
    assert job.attempt_count == 1
    assert job.last_error == "RuntimeError"
    assert calls == ["social", "events"]

    # A new worker process/factory can continue from the persisted checkpoint.
    events_available = True
    session.close()
    assert (
        run_account_erasure_jobs(
            main_dependencies.session_factory,
            max_jobs=1,
            now=utc_now() + timedelta(hours=1),
        )
        == 1
    )
    with main_dependencies.session_factory() as restarted_session:
        restarted_job = restarted_session.scalar(
            select(AccountErasureJob).where(AccountErasureJob.user_id == user_id)
        )
        user = restarted_session.get(ApplicationUser, user_id)
        assert restarted_job is not None
        assert restarted_job.current_stage == "completed"
        assert restarted_job.completed_at is not None
        assert user is not None
        assert user.status == "deleted"
        assert user.email is None
    assert calls == ["social", "events", "events", "media"]
    assert (
        run_account_erasure_jobs(
            main_dependencies.session_factory,
            max_jobs=1,
            now=utc_now() + timedelta(hours=2),
        )
        == 0
    )
    assert calls == ["social", "events", "events", "media"]


def test_worker_processes_a_persisted_job_immediately_on_startup(
    session: Session,
    monkeypatch: MonkeyPatch,
) -> None:
    client, user_id = _register()
    assert client.delete("/v1/me").status_code == 202
    monkeypatch.setattr("users.account_erasure.anonymize_social_author", lambda *_args: None)
    monkeypatch.setattr("users.account_erasure.erase_events_account", lambda *_args: None)
    monkeypatch.setattr("users.account_erasure.erase_media_assets", lambda *_args: None)

    async def run_worker_until_complete() -> None:
        stop = asyncio.Event()
        task = asyncio.create_task(
            account_erasure_worker(
                main_dependencies.session_factory,
                main_dependencies.settings,
                stop,
            )
        )
        try:
            for _ in range(500):
                await asyncio.sleep(0.01)
                with main_dependencies.session_factory() as worker_session:
                    job = worker_session.scalar(
                        select(AccountErasureJob).where(AccountErasureJob.user_id == user_id)
                    )
                    worker_user = worker_session.get(ApplicationUser, user_id)
                    if (
                        job is not None
                        and job.completed_at is not None
                        and worker_user is not None
                        and worker_user.status == "deleted"
                    ):
                        return
            raise AssertionError("startup worker did not complete persisted erasure job")
        finally:
            stop.set()
            await task

    asyncio.run(run_worker_until_complete())
    with main_dependencies.session_factory() as verification_session:
        user = verification_session.get(ApplicationUser, user_id)
        assert user is not None
        assert user.status == "deleted"
