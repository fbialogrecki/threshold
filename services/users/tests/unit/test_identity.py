import pytest
from users.domain.identity import (
    fold_username,
    is_reserved_username,
    is_valid_username,
    normalize_email,
    normalize_username,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Peregrin", "peregrin"),
        ("  Peregrin  ", "peregrin"),
        ("Żaba", "zaba"),
        ("Zaba", "zaba"),
        ("Wrocław", "wroclaw"),
        ("ĄĆĘŁŃÓŚŹŻ", "acelnoszz"),
    ],
)
def test_folding_collapses_case_and_diacritics(raw: str, expected: str) -> None:
    assert fold_username(raw) == expected


def test_lookalikes_share_one_normalized_form() -> None:
    # The whole point: one ogonek must not buy a second account.
    assert fold_username("Żaba") == fold_username("zaba")


def test_email_normalization_keeps_diacritics() -> None:
    # Folding an address would merge two distinct mailboxes.
    assert normalize_email("Zażółć@Example.COM") == "zażółć@example.com"


def test_normalized_forms_are_the_stored_lookup_keys() -> None:
    assert normalize_username("  Żaba  ") == "zaba"
    assert normalize_email("  User@Example.COM ") == "user@example.com"


@pytest.mark.parametrize(
    "username",
    ["abc", "Peregrin", "Night.Crawler-01", "Żaba_Wrocław", "a" * 30],
)
def test_valid_usernames(username: str) -> None:
    assert is_valid_username(username)


@pytest.mark.parametrize(
    "username",
    ["ab", "a" * 31, "has space", "Реregrin", "Πeregrin", "emoji🔥", "semi;colon"],
)
def test_invalid_usernames(username: str) -> None:
    assert not is_valid_username(username)


@pytest.mark.parametrize("username", ["admin", "Admin", ".admin-", "ądmin", "ROOT"])
def test_reserved_names_are_checked_after_folding(username: str) -> None:
    assert is_reserved_username(username)


def test_ordinary_names_are_not_reserved() -> None:
    assert not is_reserved_username("administrator_of_nothing")
