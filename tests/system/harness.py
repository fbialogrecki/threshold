"""Bounded, disposable local resources for the PostgreSQL/HTTP system lane.

No configurable targets: every address and credential is generated here. Podman
uses local rootless storage, never a remote connection or an implicit image pull.
"""

import json
import os
import platform
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from types import FrameType
from typing import TypedDict
from uuid import uuid4

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[2]
IMAGE = (
    "docker.io/library/postgres@sha256:"
    "1b13c640ae11f2f165d1e89667e5862b0017baf4c80fec2fb7377d86319859ba"
)
LABEL = "io.threshold.system.run"


class ResourceConfig(TypedDict, total=False):
    Labels: dict[str, str]


class OwnedResource(TypedDict, total=False):
    Id: str
    Name: str
    Config: ResourceConfig


def service_environment(inherited: Mapping[str, str] | None = None) -> dict[str, str]:
    # Intentionally no ambient values, including PATH, HOME, proxies or Python hooks.
    return {
        "PATH": os.defpath,
        "LANG": "C.UTF-8",
        "OTEL_SDK_DISABLED": "true",
        "THRESHOLD_ENVIRONMENT": "test",
        "THRESHOLD_NATS_ENABLED": "false",
        "THRESHOLD_SMTP_ENABLED": "false",
        "THRESHOLD_ACCOUNT_ERASURE_WORKER_ENABLED": "false",
        "THRESHOLD_AUTH_COOKIE_SECURE": "false",
        "THRESHOLD_AUTH_DEV_EXPOSE_TOKENS": "true",
        "THRESHOLD_AUTH_PASSWORD_PEPPER_CURRENT": secrets.token_hex(32),
        "THRESHOLD_AUTH_SESSION_TOKEN_HMAC_KEY": secrets.token_hex(32),
        "THRESHOLD_AUTH_AUDIT_HASH_KEY": secrets.token_hex(32),
    }


def require_owned(resource: OwnedResource, run: str, identifier: str) -> None:
    if (
        resource.get("Id") != identifier
        or resource.get("Name") != f"threshold-system-{run}"
        or resource.get("Config", {}).get("Labels", {}).get(LABEL) != run
    ):
        raise RuntimeError("refusing resource without positive run ownership")


class Stack:
    def __init__(self) -> None:
        self.run = uuid4().hex
        self.identifier: str | None = None
        self.create_attempted = False
        self.previous_sigterm: Callable[[int, FrameType | None], object] | int | None = None
        self.port: int | None = None
        self.passwords = {"postgres": secrets.token_hex(24)}
        self.migration_paths: dict[str, set[str]] = {}
        self.processes: list[subprocess.Popen[bytes]] = []
        self.temporary: tempfile.TemporaryDirectory[str] | None = None
        self.podman = shutil.which("podman")
        # Only the local storage/runtime coordinates needed by rootless Podman.
        self.podman_env = {key: os.environ[key] for key in ("HOME", "XDG_RUNTIME_DIR")
                           if key in os.environ}
        self.podman_env["PATH"] = os.defpath + ":/usr/sbin"

    def command(
        self, args: Sequence[str], *, env: Mapping[str, str] | None = None,
        input: str | None = None, timeout: float = 60,
    ) -> str:
        try:
            result = subprocess.run(args, env=env, input=input, cwd=ROOT, text=True,
                                    capture_output=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            raise RuntimeError("harness command timeout: execution deadline exceeded") from None
        except OSError:
            raise RuntimeError("harness command launch failed") from None
        if result.returncode:
            detail = result.stderr[-4000:]
            for value in self.passwords.values():
                detail = detail.replace(value, "[redacted]")
            raise RuntimeError(f"harness command failed (exit {result.returncode}): {detail}")
        return result.stdout

    def pod(self, *args: str, input: str | None = None, timeout: float = 60) -> str:
        assert self.podman is not None
        if args[0] == "create":
            # Defer catchable cancellation until bounded create + ID registration finish.
            mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})
            try:
                self.create_attempted = True
                result = self.command([self.podman, "--remote=false", *args],
                                      env=self.podman_env, input=input, timeout=timeout)
                self.identifier = result.strip()
                return result
            finally:
                signal.pthread_sigmask(signal.SIG_SETMASK, mask)
        return self.command([self.podman, "--remote=false", *args],
                            env=self.podman_env, input=input, timeout=timeout)

    def terminate(self, signum: int, frame: FrameType | None) -> None:
        raise SystemExit(128 + signum)

    def __enter__(self) -> "Stack":
        self.previous_sigterm = signal.signal(signal.SIGTERM, self.terminate)
        try:
            if any(name.startswith("PG") for name in os.environ):
                raise RuntimeError(
                    "unset ambient libpq PG* settings before selecting the system lane"
                )
            if not self.podman or platform.machine() != "x86_64" or sys.platform != "linux":
                raise RuntimeError("system lane requires Linux amd64 and rootless Podman")
            if self.pod("info", "--format", "{{.Host.Security.Rootless}} {{.Host.Arch}}").strip() \
                    != "true amd64":
                raise RuntimeError("system lane requires rootless amd64 Podman")
            image = json.loads(self.pod("image", "inspect", IMAGE))[0]
            if image["Architecture"] != "amd64" or image["Os"] != "linux":
                raise RuntimeError("unexpected PostgreSQL image platform")
            self.temporary = tempfile.TemporaryDirectory(prefix=f"threshold-system-{self.run}-")
            self.directory = Path(self.temporary.name)
            self.identifier = self.pod(
                "create", "--pull=never", "--name", f"threshold-system-{self.run}",
                "--label", f"{LABEL}={self.run}", "--network", "pasta",
                "--publish", "127.0.0.1::5432", "--read-only", "--read-only-tmpfs=false",
                "--tmpfs", "/var/lib/postgresql:rw,size=512m",
                "--tmpfs", "/var/run/postgresql:rw,size=16m", "--tmpfs", "/tmp:rw,size=16m",
                "--memory", "768m", "--cpus", "1", "--pids-limit", "128",
                "--security-opt", "no-new-privileges", "--env", "POSTGRES_USER=postgres",
                "--env", f"POSTGRES_PASSWORD={self.passwords['postgres']}",
                "--env", "POSTGRES_DB=postgres", IMAGE,
            ).strip()
            self.owned()
            self.pod("start", self.identifier)
            binding = json.loads(self.pod("inspect", self.identifier))[0]["NetworkSettings"][
                "Ports"]["5432/tcp"]
            if len(binding) != 1 or binding[0]["HostIp"] != "127.0.0.1":
                raise RuntimeError("PostgreSQL binding is not loopback-only")
            self.port = int(binding[0]["HostPort"])
            deadline = time.monotonic() + 45
            while True:
                try:
                    with self.connect("postgres", "postgres") as conn:
                        row = conn.execute("SHOW server_version_num").fetchone()
                        assert row is not None
                        version = row[0]
                        if version != "180003":
                            raise RuntimeError("PostgreSQL 18.3 required")
                    break
                except psycopg.OperationalError as error:
                    if time.monotonic() >= deadline:
                        logs = self.pod("logs", self.identifier)
                        for value in self.passwords.values():
                            logs = logs.replace(value, "[redacted]")
                        raise RuntimeError(f"PostgreSQL readiness deadline exceeded: {error}; "
                                           f"{logs[-3000:]}") from None
                    time.sleep(0.2)
            return self
        except BaseException:
            self.__exit__(*sys.exc_info())
            raise

    def owned(self) -> None:
        assert self.identifier is not None
        resource = json.loads(self.pod("inspect", self.identifier))[0]
        require_owned(resource, self.run, self.identifier)

    def __exit__(self, *exc: object) -> None:
        # A second TERM cannot interrupt bounded cleanup; restore caller policy afterward.
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        try:
            for process in reversed(self.processes):
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
            if self.create_attempted and not self.identifier:
                name = f"threshold-system-{self.run}"
                candidates = json.loads(self.pod("ps", "--all", "--filter", f"name={name}",
                                                  "--format", "json", timeout=10))
                if candidates:
                    resource = json.loads(self.pod("inspect", name, timeout=10))[0]
                    require_owned(resource, self.run, resource["Id"])
                    self.identifier = resource["Id"]
            if self.identifier:
                self.owned()
                self.pod("rm", "--force", self.identifier, timeout=10)
                remaining = self.pod("ps", "--all", "--filter", f"id={self.identifier}",
                                     "--format", "{{.ID}}")
                if remaining.strip():
                    raise RuntimeError("owned container cleanup was not verified")
                print(f"system cleanup verified: {self.run}")
        finally:
            try:
                if self.temporary:
                    self.temporary.cleanup()
            finally:
                if self.previous_sigterm is not None:
                    signal.signal(signal.SIGTERM, self.previous_sigterm)

    def connect(self, database: str, role: str) -> psycopg.Connection[tuple[object, ...]]:
        # Explicit connection parameters: no ambient PG credentials/host/service/passfile.
        return psycopg.connect(
            host="127.0.0.1", hostaddr="127.0.0.1", port=self.port, dbname=database,
            user=role, password=self.passwords[role], passfile="/dev/null",
            sslmode="disable", gssencmode="disable", connect_timeout=2,
            options="-c statement_timeout=10000 -c lock_timeout=3000", autocommit=True,
        )

    def url(self, database: str, role: str) -> str:
        return (f"postgresql+psycopg://{role}:{self.passwords[role]}"
                f"@127.0.0.1:{self.port}/{database}?connect_timeout=3")

    def migrate(self, service: str, database: str, revision: str | None = None) -> None:
        env = service_environment()
        env["THRESHOLD_DATABASE_URL"] = self.url(database, f"{service}_owner")
        args = [sys.executable, "-m", f"{service}.migrate"]
        if revision:
            args = [sys.executable, "-c",
                    f"from {service}.migrate import build_config; from alembic import command; "
                    f"command.upgrade(build_config(), {revision!r})"]
        # Logs contain only synthetic data and stay in a mode-0700 disposable directory.
        result = subprocess.run(args, env=env, cwd=self.directory, text=True,
                                capture_output=True, timeout=60, check=False)
        log = self.directory / f"{database}-migration.log"
        log.write_text(result.stdout + result.stderr)
        if result.returncode:
            # No URL/secret exposure; exception type + migration messages are available
            # for local debugging before fixture cleanup, not published automatically.
            raise RuntimeError(f"production {service} migration failed (exit {result.returncode})")

    def prepare_databases(self) -> None:
        from alembic.script import ScriptDirectory
        from social.migrate import build_config as social_config
        from users.migrate import build_config as users_config

        for service, config in (("users", users_config), ("social", social_config)):
            scripts = ScriptDirectory.from_config(config())
            heads = scripts.get_heads()
            assert len(heads) == 1, "system fixture requires an explicit single production head"
            head = heads[0]
            revision = scripts.get_revision(head)
            assert revision is not None
            previous = revision.down_revision
            assert isinstance(previous, str)
            owner, runtime = f"{service}_owner", f"{service}_runtime"
            with self.connect("postgres", "postgres") as conn:
                for role in (owner, runtime):
                    self.passwords[role] = secrets.token_hex(24)
                    conn.execute(sql.SQL(
                        "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB "
                        "NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}"
                    ).format(sql.Identifier(role), sql.Literal(self.passwords[role])))
                for database in (service, f"{service}_previous"):
                    conn.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(
                        sql.Identifier(database), sql.Identifier(owner)))
                    conn.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(
                        sql.Identifier(database)))
                conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    sql.Identifier(service), sql.Identifier(runtime)))
            self.migration_paths[service] = set()
            for database, path in ((service, "empty"), (f"{service}_previous", "predecessor")):
                with self.connect(database, owner) as conn:
                    conn.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
                if path == "predecessor":
                    self.migrate(service, database, previous)
                    self.seed_previous(service, database)
                self.migrate(service, database)
                with self.connect(database, owner) as conn:
                    assert conn.execute("SELECT version_num FROM alembic_version").fetchall() \
                        == [(head,)]
                    if path == "predecessor":
                        if service == "users":
                            assert conn.execute("SELECT username_normalized FROM application_users "
                                                "WHERE username = 'Żaba_Fixture'").fetchone() \
                                == ("zaba_fixture",)
                        else:
                            assert conn.execute("SELECT name FROM groups WHERE slug = "
                                                "'previous-fixture'").fetchone() == ("Previous",)
                    self.migration_paths[service].add(path)
            with self.connect(service, owner) as conn:
                conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(
                    sql.Identifier(runtime)))
                conn.execute(sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES "
                                     "IN SCHEMA public TO {}").format(sql.Identifier(runtime)))
                conn.execute(sql.SQL("REVOKE ALL ON alembic_version FROM {}").format(
                    sql.Identifier(runtime)))
                conn.execute(sql.SQL("GRANT SELECT ON alembic_version TO {}").format(
                    sql.Identifier(runtime)))
                conn.execute(sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}")
                             .format(sql.Identifier(runtime)))
            print(f"{service}: empty + synthetic predecessor -> {head}")

    def seed_previous(self, service: str, database: str) -> None:
        with self.connect(database, f"{service}_owner") as conn:
            if service == "users":
                conn.execute("INSERT INTO application_users "
                             "(id, username, username_normalized, status, identity_source, "
                             "created_at, updated_at) VALUES (%s, 'Żaba_Fixture', 'żaba_fixture', "
                             "'active', 'product', now(), now())", (str(uuid4()),))
            else:
                conn.execute("INSERT INTO groups (id, slug, name, city, official, created_at) "
                             "VALUES (%s, 'previous-fixture', 'Previous', "
                             "'Synthetic', true, now())",
                             (str(uuid4()),))

    def service_diagnostics(self, service: str) -> str:
        # Read only a bounded tail of this run's synthetic logs, before cleanup.
        with (self.directory / f"{service}.log").open("rb") as log:
            log.seek(0, 2)
            log.seek(max(0, log.tell() - 4000))
            detail = log.read(4000).decode("utf-8", errors="replace")
        for value in (*self.passwords.values(), self.token):
            detail = detail.replace(value, "[redacted]")
        return detail

    def start_services(self) -> None:
        import httpx

        self.token = secrets.token_hex(32)
        self.urls: dict[str, str] = {}
        for service in ("users", "social"):
            env = service_environment()
            env["THRESHOLD_DATABASE_URL"] = self.url(service, f"{service}_runtime")
            env["THRESHOLD_INTERNAL_TOKEN"] = self.token
            if service == "social":
                env["USERS_SERVICE_URL"] = self.urls["users"]
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                listener.listen(128)
                self.urls[service] = f"http://127.0.0.1:{listener.getsockname()[1]}"
                with (self.directory / f"{service}.log").open("wb") as log:
                    process = subprocess.Popen(
                        [sys.executable, "-m", "uvicorn", f"{service}.main:app",
                         "--fd", str(listener.fileno()), "--workers", "1",
                         "--no-access-log", "--log-level", "warning"],
                        env=env, cwd=self.directory, pass_fds=(listener.fileno(),),
                        stdout=log, stderr=subprocess.STDOUT,
                    )
                    self.processes.append(process)
            deadline = time.monotonic() + 30
            last_state = "no response"
            with httpx.Client(base_url=self.urls[service], trust_env=False, timeout=1) as client:
                while True:
                    if process.poll() is not None:
                        raise RuntimeError(f"{service} process exited before readiness: "
                                           f"{self.service_diagnostics(service)}")
                    try:
                        response = client.get("/readyz")
                        last_state = f"HTTP {response.status_code}"
                        if response.status_code == 200:
                            break
                    except httpx.TransportError as error:
                        last_state = type(error).__name__
                    if time.monotonic() >= deadline:
                        raise RuntimeError(f"{service} HTTP readiness deadline exceeded: "
                                           f"{last_state}; "
                                           f"{self.service_diagnostics(service)}")
                    time.sleep(0.1)

    def verify_runtime_roles(self) -> None:
        for service, other in (("users", "social"), ("social", "users")):
            runtime = f"{service}_runtime"
            with self.connect(service, runtime) as conn:
                assert conn.execute("SELECT current_user").fetchone() == (runtime,)
                # Production /readyz reads the migration marker, never writes it.
                assert conn.execute("SELECT version_num FROM alembic_version").fetchone()
                for statement in ("CREATE TABLE forbidden (id int)",
                                  "UPDATE alembic_version SET version_num = 'forbidden'",
                                  f"SET ROLE {service}_owner"):
                    try:
                        conn.execute(statement)
                    except psycopg.errors.InsufficientPrivilege:
                        pass
                    else:
                        raise AssertionError("runtime role can migrate or assume owner")
            try:
                with self.connect(other, runtime):
                    raise AssertionError("runtime can connect to the other domain database")
            except psycopg.OperationalError as error:
                assert "permission denied for database" in str(error)
