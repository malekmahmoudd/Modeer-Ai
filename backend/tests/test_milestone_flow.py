"""The first-milestone end-to-end flow (see the brief).

Modeer learns a durable fact -> it lands in shared context -> Career and Study
each pick it up for their own domain -> conversations stay independent -> the
fact is editable and deletable through the memory API.
"""
from __future__ import annotations

FACT_MSG = (
    "Just so you know, I am studying mechanical engineering at TU Delft, "
    "and I'm preparing for my thermodynamics final."
)


def _chat(client, agent, message, conversation_id=None):
    body = {"message": message}
    if conversation_id:
        body["conversation_id"] = conversation_id
    r = client.post(f"/api/agents/{agent}/chat", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_full_milestone_flow(client):
    # 1-3. User tells Modeer a durable fact; it is captured into shared context.
    res = _chat(client, "modeer", FACT_MSG)
    stored = [c for c in res["memory_candidates"] if c["stored"]]
    assert any(c["scope"] == "shared" and "mechanical engineering" in c["value"]
               for c in stored)

    shared = client.get("/api/memory/shared").json()
    fact = next(m for m in shared if m["value"].startswith("mechanical engineering"))
    assert fact["category"] == "education"
    assert fact["source"] == "modeer"

    # 4-6. Go straight to the Career Agent — no routing through Modeer.
    career = _chat(client, "career", "Given all that, what should I focus on next?")
    assert career["context_used"] is True
    assert "mechanical engineering" in career["content"]

    # 7-8. Study Agent uses the same shared fact for its own domain.
    study = _chat(client, "study", "Plan my next two weeks of study.")
    assert "mechanical engineering" in study["content"]

    # 9. Independent conversation histories.
    assert career["conversation_id"] != study["conversation_id"]
    career_convo = client.get(
        f"/api/conversations/{career['conversation_id']}"
    ).json()
    study_convo = client.get(
        f"/api/conversations/{study['conversation_id']}"
    ).json()
    assert career_convo["agent_id"] == "career"
    assert study_convo["agent_id"] == "study"
    career_texts = " ".join(m["content"] for m in career_convo["messages"])
    assert "Plan my next two weeks" not in career_texts

    # 10. The stored fact is editable and deletable via the memory UI API.
    patched = client.patch(
        f"/api/memory/shared/{fact['id']}",
        json={"value": "mechanical engineering (switched focus to robotics)"},
    )
    assert patched.status_code == 200
    assert "robotics" in patched.json()["value"]

    deleted = client.delete(f"/api/memory/shared/{fact['id']}")
    assert deleted.status_code == 204
    assert all(m["id"] != fact["id"] for m in client.get("/api/memory/shared").json())


def test_conversation_continuity_with_conversation_id(client):
    first = _chat(client, "study", "Teach me about entropy.")
    cid = first["conversation_id"]
    second = _chat(client, "study", "Now relate it to my course.", conversation_id=cid)
    assert second["conversation_id"] == cid
    convo = client.get(f"/api/conversations/{cid}").json()
    # 2 user + 2 assistant
    assert len(convo["messages"]) == 4


def test_streaming_endpoint_emits_sse_events(client):
    with client.stream(
        "POST", "/api/agents/study/chat/stream", json={"message": "hello"}
    ) as r:
        assert r.status_code == 200
        assert "text/event-stream" in r.headers["content-type"]
        body = "".join(r.iter_text())
    assert '"type": "start"' in body
    assert '"type": "delta"' in body
    assert '"type": "end"' in body
