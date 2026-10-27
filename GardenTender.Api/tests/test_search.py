from tests.support import GLOBAL_ADMIN, create_garden, login, onboard


def search(client, q):
    return client.get("/users/search", params={"q": q})


def test_search_requires_membership(client):
    onboard(client, "auth0|ann")
    assert search(client, "an").status_code == 403


def test_search_by_prefix_without_email(client):
    onboard(client, "auth0|ann", "ann_lee")
    onboard(client, "auth0|annie")
    onboard(client, "auth0|bob")
    login(sub="auth0|anna")
    client.get("/me")  # exists but never onboarded: excluded
    create_garden(client, "auth0|bob")
    login(sub="auth0|bob")
    assert search(client, "@AN").json() == [
        {"handle": "ann_lee", "display_name": "Ann_Lee"},
        {"handle": "annie", "display_name": "Annie"},
    ]


def test_search_escapes_wildcards(client):
    onboard(client, "auth0|ann", "ann_lee")
    onboard(client, "auth0|annxlee")
    create_garden(client, "auth0|ann")
    login(sub="auth0|ann")
    assert [u["handle"] for u in search(client, "ann_").json()] == ["ann_lee"]


def test_search_minimum_length(client):
    onboard(client, "auth0|ann")
    create_garden(client, "auth0|ann")
    login(sub="auth0|ann")
    assert search(client, "a").status_code == 400


def test_global_admin_can_search(client):
    onboard(client, "auth0|ann")
    login(GLOBAL_ADMIN, sub="auth0|root")
    assert search(client, "an").json()[0]["handle"] == "ann"
