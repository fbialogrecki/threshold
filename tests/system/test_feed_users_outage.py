"""A stopped owned users process must not produce a successful unfiltered feed."""

from collections.abc import Iterator

import pytest

from .harness import Stack
from .test_blocks_http import FeedCase
from .test_blocks_http import feed_case as feed_case


@pytest.fixture()
def http_stack() -> Iterator[Stack]:
    # Separate ownership scope: do not stop a process shared by other tests.
    with Stack() as stack:
        stack.prepare_databases()
        stack.start_services()
        yield stack


def test_owned_users_process_outage_fails_closed(feed_case: FeedCase) -> None:
    stack, viewer, viewer_user, author_user, social, headers, post_id = feed_case
    # feed_case already asserted a healthy, nonempty real HTTP feed.
    for process in stack.processes:
        assert isinstance(process.args, (str, list, tuple))
    users = [p for p in stack.processes
             if isinstance(p.args, (str, list, tuple)) and "users.main:app" in p.args]
    assert len(users) == 1
    assert users[0].poll() is None
    users[0].terminate()
    users[0].wait(timeout=10)
    assert users[0].poll() is not None
    assert social.get("/healthz").status_code == 200
    response = social.get("/v1/feed", headers=headers(viewer_user))
    assert response.status_code == 503
    assert "items" not in response.json()
    assert post_id not in response.text
