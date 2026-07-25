from pathlib import Path

import pytest
from alembic.script import ScriptDirectory
from users.migrate import build_config

import users


def _script_dir() -> Path:
    return Path(ScriptDirectory.from_config(build_config()).dir)


def test_migrations_resolve_from_any_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert (_script_dir() / "env.py").is_file()


def test_migrations_live_inside_the_importable_package() -> None:
    # The wheel ships only the package directory, so anything resolved outside
    # it disappears on `uv sync --no-editable` while still passing in a source
    # checkout. Containment is what makes this test prove the installed layout.
    assert _script_dir().is_relative_to(Path(users.__file__).parent)
