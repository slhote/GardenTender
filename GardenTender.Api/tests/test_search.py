from tests.support import GLOBAL_ADMIN, create_garden, login, onboard


async def search(client, q):
    return await client.get("/users/search", params={"q": q})


async def test_search_requires_membership(client):
    await onboard(client, "auth0|ann")
    assert (await search(client, "an")).status_code == 403


async def test_search_by_prefix_without_email(client):
    await onboard(client, "auth0|ann", "ann_lee")
    await onboard(client, "auth0|annie")
    await onboard(client, "auth0|bob")
    login(sub="auth0|anna")
    await client.get("/me")  # exists but never onboarded: excluded
    await create_garden(client, "auth0|bob")
    login(sub="auth0|bob")
    found = (await search(client, "@AN")).json()
    # Ordered by handle, but how "_" sorts depends on the database collation, so compare as a set.
    assert sorted(found, key=lambda u: u["handle"]) == [
        {"handle": "ann_lee", "display_name": "Ann_Lee"},
        {"handle": "annie", "display_name": "Annie"},
    ]


async def test_search_escapes_wildcards(client):
    await onboard(client, "auth0|ann", "ann_lee")
    await onboard(client, "auth0|annxlee")
    await create_garden(client, "auth0|ann")
    login(sub="auth0|ann")
    assert [u["handle"] for u in (await search(client, "ann_")).json()] == ["ann_lee"]


async def test_search_minimum_length(client):
    await onboard(client, "auth0|ann")
    await create_garden(client, "auth0|ann")
    login(sub="auth0|ann")
    assert (await search(client, "a")).status_code == 400


async def test_global_admin_can_search(client):
    await onboard(client, "auth0|ann")
    login(GLOBAL_ADMIN, sub="auth0|root")
    assert (await search(client, "an")).json()[0]["handle"] == "ann"
