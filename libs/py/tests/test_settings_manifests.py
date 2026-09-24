"""Every service setting the cluster must provide is wired in infra/.

A Settings field without a manifest entry silently falls back to its default
in the cluster (USERS_SERVICE_URL and EVENTS_SERVICE_URL were both missed
that way). Fields that point at another system (`*_url`) or have no usable
default (`None`) must reach the service's container through its env or an
`envFrom` ConfigMap/Secret defined somewhere under infra/kustomize/base.
"""

import importlib
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]
from pydantic_settings import BaseSettings

BASE = Path(__file__).resolve().parents[3] / "infra" / "kustomize" / "base"
SERVICES = {
    "auth-gateway": "auth_gateway",
    "events": "events",
    "media": "media",
    "social": "social",
    "users": "users",
}
# Settings that are deliberately not set in the cluster, with the reason.
NOT_DEPLOYED: dict[str, set[str]] = {
    # Only needed for the SSO -> users lookup, which is not enabled yet.
    "auth-gateway": {"THRESHOLD_AUTHENTIK_AUDIENCE", "THRESHOLD_INTERNAL_TOKEN"},
    # Falls back to the system temp dir.
    "media": {"THRESHOLD_UPLOAD_TEMP_DIR"},
    # Declared but not read by the service.
    "social": {"THRESHOLD_MEDIA_SERVICE_URL"},
    "users": {
        # Set only while rotating the pepper.
        "THRESHOLD_AUTH_PASSWORD_PEPPER_PREVIOUS",
        # SMTP credentials wait for ExternalSecret/users-email (open MVP gate in AGENTS.md).
        "THRESHOLD_SMTP_USERNAME",
        "THRESHOLD_SMTP_PASSWORD",
        "THRESHOLD_SMTP_CA_FILE",
    },
}


def env_name(name: str, field: Any, prefix: str) -> str:
    alias = field.validation_alias
    return alias if isinstance(alias, str) else f"{prefix}{name}".upper()


def must_be_wired(settings: type[BaseSettings]) -> set[str]:
    prefix = settings.model_config.get("env_prefix", "")
    return {
        env_name(name, field, prefix)
        for name, field in settings.model_fields.items()
        if name.endswith("_url") or (not field.is_required() and field.default is None)
    }


def documents(directory: Path) -> list[dict[str, Any]]:
    docs = []
    for path in directory.rglob("*.yaml"):
        docs += [doc for doc in yaml.safe_load_all(path.read_text()) if isinstance(doc, dict)]
    return docs


def env_sources() -> dict[str, set[str]]:
    """Keys provided by every ConfigMap and ExternalSecret target, by object name."""
    sources: dict[str, set[str]] = {}
    for doc in documents(BASE):
        spec = doc.get("spec") or {}
        if doc.get("kind") == "ConfigMap":
            sources.setdefault(doc["metadata"]["name"], set()).update(doc.get("data") or {})
        elif doc.get("kind") == "ExternalSecret":
            target = spec.get("target") or {}
            keys = {item["secretKey"] for item in spec.get("data") or []}
            keys |= set((target.get("template") or {}).get("data") or {})
            name = target.get("name") or doc["metadata"]["name"]
            sources.setdefault(name, set()).update(keys)
    return sources


def container_env(service: str) -> set[str]:
    sources = env_sources()
    keys: set[str] = set()
    for doc in documents(BASE / service):
        if doc.get("kind") != "Deployment":
            continue
        for container in doc["spec"]["template"]["spec"]["containers"]:
            keys |= {env["name"] for env in container.get("env") or []}
            for ref in container.get("envFrom") or []:
                source = ref.get("configMapRef") or ref.get("secretRef") or {}
                keys |= sources.get(source.get("name", ""), set())
    return keys


@pytest.mark.parametrize("service", sorted(SERVICES))
def test_settings_are_wired_in_manifests(service: str) -> None:
    module = importlib.import_module(f"{SERVICES[service]}.settings")
    missing = must_be_wired(module.Settings) - container_env(service)
    missing -= NOT_DEPLOYED.get(service, set())
    assert not missing, f"{service}: wire in infra/kustomize/base/{service}/: {sorted(missing)}"
