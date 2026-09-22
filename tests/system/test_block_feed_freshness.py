"""Additional canonical feed checks over real sockets and committed PostgreSQL."""

from .test_blocks_http import FeedCase, User
from .test_blocks_http import feed_case as feed_case


def test_reverse_block_and_unblock_are_fresh(feed_case: FeedCase) -> None:
    stack, viewer, viewer_user, author_user, social, headers, post_id = feed_case
    with stack.connect("social", "social_runtime") as conn:
        row = conn.execute(
            "SELECT groups.slug FROM groups JOIN posts ON posts.group_id = groups.id "
            "WHERE posts.id = %s",
            (post_id,),
        ).fetchone()
        assert row is not None
        slug = row[0]
    post = social.post(
        "/v1/posts",
        headers=headers(viewer_user),
        json={"body": "Reverse block control", "group_slug": slug},
    )
    assert post.status_code == 201
    reverse_post_id = post.json()["id"]

    def ids(user: User) -> set[object]:
        response = social.get("/v1/feed", headers=headers(user))
        assert response.status_code == 200
        return {item["id"] for item in response.json()["items"]}

    assert reverse_post_id in ids(author_user)
    assert (
        viewer.post("/v1/me/blocks", json={"username": author_user["username"]}).status_code == 201
    )
    assert reverse_post_id not in ids(author_user)
    assert post_id not in ids(viewer_user)
    assert viewer.delete(f"/v1/me/blocks/{author_user['username']}").status_code == 204
    assert reverse_post_id in ids(author_user)
    assert post_id in ids(viewer_user)
