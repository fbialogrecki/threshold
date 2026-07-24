"""Public identity rules: one name per person, defined in exactly one place.

The username is the only public name for a person, so uniqueness has to be
stricter than a case fold. `Żaba` and `Zaba` differ by one ogonek, which is easy
to miss and therefore an invitation to impersonate, so both collapse onto the
same normalised form and only one of them can exist. The stored `username`
keeps whatever form its owner typed; only `username_normalized` is folded.

Everything here lives in one module because three copies of this logic used to
disagree quietly. The login path in particular compared a `.strip().lower()`
subject against a folded column, which would have locked out every account with
a diacritic in its name.
"""

import re
import unicodedata

USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 30

# Explicit character set, never \w or \p{L}: a broad class would admit Cyrillic
# and Greek lookalikes, which is exactly the impersonation route the folding
# below exists to close.
_USERNAME_CHARS = r"A-Za-z0-9_.\-ąćęłńóśźżĄĆĘŁŃÓŚŹŻ"
USERNAME_PATTERN = rf"[{_USERNAME_CHARS}]{{{USERNAME_MIN_LENGTH},{USERNAME_MAX_LENGTH}}}"
USERNAME_RE = re.compile(rf"\A{USERNAME_PATTERN}\Z")

RESERVED_USERNAMES = frozenset({"admin", "root", "support", "threshold"})

# ł and Ł are the one Polish pair NFKD will not decompose, so they need an
# explicit mapping; the rest lose their combining marks below.
_EXPLICIT_FOLD = str.maketrans({"ł": "l", "Ł": "l"})


def fold_username(username: str) -> str:
    """Case-folded, diacritic-folded form used for uniqueness and lookups."""
    lowered = username.strip().lower().translate(_EXPLICIT_FOLD)
    decomposed = unicodedata.normalize("NFKD", lowered)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def normalize_username(username: str) -> str:
    """Stored in `username_normalized`; the unique index compares this form."""
    return fold_username(username)


def normalize_email(email: str) -> str:
    """Emails only case-fold: folding diacritics here would merge distinct addresses."""
    return email.strip().lower()


def is_valid_username(username: str) -> bool:
    return USERNAME_RE.fullmatch(username) is not None


def is_reserved_username(username: str) -> bool:
    """Reserved names are checked after folding, so `ądmin` cannot claim `admin`."""
    return fold_username(username).strip("_.-") in RESERVED_USERNAMES
