"""Control-plane unit tests: no container or application substitutes."""

import importlib.util
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol, runtime_checkable

import pytest

from .harness import OwnedResource, Stack


@runtime_checkable
class HarnessModule(Protocol):
    Stack: type[Stack]

    def require_owned(self, resource: OwnedResource, run: str, identifier: str) -> None: ...

    def service_environment(
        self, inherited: Mapping[str, str] | None = None,
    ) -> dict[str, str]: ...


def harness_module() -> HarnessModule:
    path = Path(__file__).with_name("harness.py")
    assert path.is_file(), "run-owned resource fence is not implemented"
    spec = importlib.util.spec_from_file_location("safety_harness", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert isinstance(module, HarnessModule)
    return module


@pytest.mark.parametrize("change", ["label", "name", "id", "missing"])
def test_cleanup_rejects_resources_not_positively_owned(change: str) -> None:
    harness = harness_module()
    run = "a" * 32
    identifier = "b" * 64
    resource: OwnedResource = {
        "Id": identifier,
        "Name": f"threshold-system-{run}",
        "Config": {"Labels": {"io.threshold.system.run": run}},
    }
    if change == "label":
        resource["Config"]["Labels"]["io.threshold.system.run"] = "other"
    elif change == "name":
        resource["Name"] = "operator-postgres"
    elif change == "id":
        resource["Id"] = "c" * 64
    else:
        resource = {}
    with pytest.raises(RuntimeError, match="ownership"):
        harness.require_owned(resource, run, identifier)


def test_service_environment_does_not_inherit_operator_values() -> None:
    harness = harness_module()
    assert hasattr(harness, "service_environment"), "environment fence is not implemented"
    inherited = {
        "PATH": "/operator/bin", "HOME": "/operator", "PYTHONPATH": "/operator/code",
        "THRESHOLD_DATABASE_URL": "postgresql://operator/live", "USERS_SERVICE_URL": "https://live",
        "HTTP_PROXY": "http://proxy", "https_proxy": "http://proxy",
        "OTEL_EXPORTER_OTLP_ENDPOINT": "https://live", "THRESHOLD_SMTP_ENABLED": "true",
        "PGPASSWORD": "operator", "AWS_ACCESS_KEY_ID": "operator",
    }
    env = harness.service_environment(inherited)
    assert all(env.get(key) != value for key, value in inherited.items())
    for name in ("THRESHOLD_NATS_ENABLED", "THRESHOLD_SMTP_ENABLED",
                 "THRESHOLD_ACCOUNT_ERASURE_WORKER_ENABLED"):
        assert env[name] == "false"
    assert env["OTEL_SDK_DISABLED"] == "true"
