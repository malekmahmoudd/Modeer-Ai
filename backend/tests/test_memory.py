from __future__ import annotations

from app.agents.registry import require_agent
from app.memory import service
from app.memory.extraction import extract_candidates
from app.memory.schemas import AgentMemoryCreate, SharedMemoryCreate

# --- extraction ------------------------------------------------------------

def test_durable_shared_fact_is_extracted():
    cands = extract_candidates(
        "I am studying mechanical engineering at TU Delft.", agent_id="modeer"
    )
    stored = [c for c in cands if c.stored]
    assert any(c.category == "education" and "mechanical engineering" in c.value
               for c in stored)


def test_transient_detail_is_not_stored():
    cands = extract_candidates("I'm so tired today, good morning!", agent_id="modeer")
    assert all(not c.stored for c in cands)


def test_sensitive_fact_is_flagged_and_not_stored_by_default():
    cands = extract_candidates(
        "I was diagnosed with depression and my salary is 42000.", agent_id="modeer"
    )
    assert cands, "expected at least one flagged candidate"
    assert all(not c.stored for c in cands)
    assert any(c.sensitive for c in cands)


def test_agent_scoped_rule_only_fires_in_its_own_agent():
    in_study = extract_candidates("I learn best by drawing diagrams.", agent_id="study")
    in_travel = extract_candidates("I learn best by drawing diagrams.", agent_id="travel")
    assert any(c.scope == "agent" and c.agent_id == "study" for c in in_study)
    assert not any(c.scope == "agent" for c in in_travel)


# --- persistence & isolation --------------------------------------------

def test_shared_memory_is_isolated_between_users(db, make_user):
    a = make_user("Ann")
    b = make_user("Bob")
    service.upsert_shared(db, a.id, SharedMemoryCreate(
        category="context", key="location", value="Cairo"))
    db.commit()
    assert [m.value for m in service.list_shared(db, a.id)] == ["Cairo"]
    assert service.list_shared(db, b.id) == []


def test_agent_memory_namespaced_and_not_visible_to_other_agents(db, make_user):
    u = make_user("Cara")
    service.upsert_agent(db, u.id, AgentMemoryCreate(
        agent_id="study", category="weak_topics", key="weak_topic", value="integrals"))
    db.commit()
    assert len(service.list_agent(db, u.id, "study")) == 1
    assert service.list_agent(db, u.id, "career") == []


def test_context_for_agent_excludes_unwanted_categories(db, make_user):
    u = make_user("Dave")
    service.upsert_shared(db, u.id, SharedMemoryCreate(
        category="education", key="major", value="physics"))
    service.upsert_shared(db, u.id, SharedMemoryCreate(
        category="context", key="location", value="Oslo"))
    db.commit()
    shared, _ = service.context_for_agent(db, u.id, require_agent("study"))
    cats = {m.category for m in shared}
    assert "education" in cats
    # study wants education/goals/context -> location included too
    assert "context" in cats

    shared_email, _ = service.context_for_agent(db, u.id, require_agent("email"))
    # email wants career/context only -> education excluded
    assert "education" not in {m.category for m in shared_email}


def test_upsert_shared_updates_existing_key(db, make_user):
    u = make_user("Eve")
    service.upsert_shared(db, u.id, SharedMemoryCreate(
        category="context", key="location", value="Rome"))
    service.upsert_shared(db, u.id, SharedMemoryCreate(
        category="context", key="location", value="Milan"))
    db.commit()
    rows = service.list_shared(db, u.id)
    assert len(rows) == 1 and rows[0].value == "Milan"
