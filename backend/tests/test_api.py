from __future__ import annotations


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["agents"] == 10
    assert body["llm_provider"] == "mock"


def test_list_agents_shape(client):
    agents = client.get("/api/agents").json()
    assert len(agents) == 10
    modeer = next(a for a in agents if a["id"] == "modeer")
    assert modeer["is_assistant"] is True
    assert {"name", "role", "icon", "accent", "description"} <= set(modeer)


def test_agent_detail_exposes_framework(client):
    detail = client.get("/api/agents/study").json()
    assert detail["reasoning_framework"]
    assert detail["memory_namespace"] == "study"
    assert client.get("/api/agents/does-not-exist").status_code == 404


def test_goals_crud(client):
    created = client.post("/api/goals", json={"title": "Ship the MVP", "priority": 1})
    assert created.status_code == 201
    gid = created.json()["id"]

    assert any(g["id"] == gid for g in client.get("/api/goals").json())

    upd = client.patch(f"/api/goals/{gid}", json={"status": "done"})
    assert upd.status_code == 200 and upd.json()["status"] == "done"

    assert client.delete(f"/api/goals/{gid}").status_code == 204
    assert client.get("/api/goals").json() == []


def test_briefing_today_uses_only_stored_data(client):
    client.post("/api/goals", json={"title": "Finish the internship CV", "priority": 1})
    b = client.get("/api/briefings/today").json()
    assert "Finish the internship CV" in " ".join(i["text"] for i in b["items"])
    assert b["generated_for_date"]
    # idempotent for the day
    b2 = client.get("/api/briefings/today").json()
    assert b2["id"] == b["id"]


def test_user_isolation_via_header(client):
    # demo user stores a fact
    client.post("/api/agents/modeer/chat", json={"message": "I live in Lisbon."})
    demo_shared = client.get("/api/memory/shared").json()
    assert any("Lisbon" in m["value"] for m in demo_shared)

    # a different explicit user starts empty
    make = client.post("/api/goals", json={"title": "x"})  # ensure demo exists
    assert make.status_code == 201
    r = client.get("/api/memory/shared", headers={"X-User-Id": "not-a-real-user"})
    assert r.status_code == 404


def test_agent_memory_endpoint_isolation(client):
    client.post(
        "/api/memory/agent",
        json={"agent_id": "study", "category": "prefs", "key": "style",
              "value": "diagrams"},
    )
    assert len(client.get("/api/memory/agent/study").json()) == 1
    assert client.get("/api/memory/agent/career").json() == []


def test_ask_my_team_is_explicit_and_multi_specialist(client):
    client.post("/api/agents/modeer/chat", json={"message": "I live in Nairobi."})
    r = client.post(
        "/api/team/ask",
        json={"question": "Should I do a bootcamp?", "agent_ids": ["career", "study"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert {t["agent_id"] for t in body["takes"]} == {"career", "study"}
    assert body["synthesis"]
