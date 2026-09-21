"""PATCH omission/null semantics through the real routes and persistence layer."""

import pytest


def resource(client, kind):
    if kind == "profile":
        path = "/api/users/me"
        client.get(path)  # Create the demo account, then compare persisted reads.
        return path, path, client.get(path).json()
    if kind == "goal":
        collection = "/api/goals"
        body = {"title": "Keep this goal", "detail": "Keep this detail"}
    elif kind == "shared":
        collection = "/api/memory/shared"
        body = {"key": "keep", "value": "Keep this fact"}
    else:
        collection = "/api/memory/agent"
        body = {"agent_id": "study", "key": "keep", "value": "Keep this private fact"}
    result = client.post(collection, json=body)
    assert result.status_code == 201
    record = result.json()
    read = collection + "/study" if kind == "agent" else collection
    return collection + "/" + record["id"], read, client.get(read).json()


NULL_CASES = [
    (kind, field)
    for kind, fields in {
        "profile": ["display_name", "profile", "onboarded", "memory_auto"],
        "goal": ["title", "detail", "priority", "status"],
        "shared": ["category", "key", "value", "confidence", "sensitive", "pinned"],
        "agent": ["category", "key", "value", "confidence", "sensitive"],
    }.items()
    for field in fields
]


@pytest.mark.parametrize("kind,field", NULL_CASES)
def test_explicit_null_rejected_without_mutation(client, kind, field):
    path, read, before = resource(client, kind)
    response = client.patch(path, json={field: None})
    assert response.status_code == 422, response.text
    assert any(
        item["loc"][-1] == field and "must not be null" in item["msg"]
        for item in response.json()["detail"]
    )
    assert client.get(read).json() == before


@pytest.mark.parametrize("kind", ["profile", "goal", "shared", "agent"])
def test_omitted_fields_are_not_null_updates(client, kind):
    path, read, before = resource(client, kind)
    assert client.patch(path, json={}).status_code == 200
    assert client.get(read).json() == before


def test_nullable_target_date_can_still_be_cleared(client):
    goal = client.post(
        "/api/goals", json={"title": "Deadline", "target_date": "2026-10-01T00:00:00Z"}
    ).json()
    response = client.patch(f"/api/goals/{goal['id']}", json={"target_date": None})
    assert response.status_code == 200
    assert response.json()["target_date"] is None
    assert response.json()["title"] == "Deadline"


def test_nullable_email_can_still_be_cleared_for_key_account(client):
    assert client.patch("/api/users/me", json={"email": "review@example.com"}).status_code == 200
    response = client.patch("/api/users/me", json={"email": None})
    assert response.status_code == 200
    assert response.json()["email"] is None
