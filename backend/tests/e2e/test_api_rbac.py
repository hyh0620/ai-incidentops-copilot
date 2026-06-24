from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.database import get_session
from app.main import app
from app.models import AIReview, KnowledgeBaseArticle, Ticket, User, UserRole
from app.services.rag_service import rebuild_kb_index


def _client(tmp_path: Path) -> tuple[TestClient, Session]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
    session.add_all(
        [
            User(id=1, name="Requester A", email="a@example.com", role=UserRole.requester, department="A"),
            User(id=2, name="Requester B", email="b@example.com", role=UserRole.requester, department="B"),
            User(id=7, name="Admin", email="admin@example.com", role=UserRole.admin, department="IT"),
        ]
    )
    session.add(KnowledgeBaseArticle(title="VPN 无法连接", category="网络连接", summary="vpn", content="VPN cannot connect network timeout", tags=["vpn"]))
    session.commit()
    import app.services.rag_service as rag_service

    rag_service.DEFAULT_INDEX_DIR = tmp_path / "index"
    rebuild_kb_index(session, index_dir=rag_service.DEFAULT_INDEX_DIR, force_fallback=True)

    def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    return TestClient(app), session


def test_protected_apis_require_demo_persona_header(tmp_path: Path):
    client, _ = _client(tmp_path)

    tickets = client.get("/api/tickets")
    reviews = client.get("/api/ai/reviews")
    users = client.get("/api/users")

    assert tickets.status_code == 401
    assert reviews.status_code == 401
    assert users.status_code == 401
    assert "X-Demo-User-Id" in tickets.json()["error"]["message"]
    assert "Demo Persona" in tickets.json()["error"]["message"]
    app.dependency_overrides.clear()


def test_requester_cannot_read_other_ticket(tmp_path: Path):
    client, session = _client(tmp_path)
    ticket = Ticket(requester_id=1, title="VPN cannot connect", description="VPN cannot connect", user_category="网络连接", urgency="中")
    session.add(ticket)
    session.commit()
    session.refresh(ticket)

    own = client.get(f"/api/tickets/{ticket.id}", headers={"X-Demo-User-Id": "1"})
    other = client.get(f"/api/tickets/{ticket.id}", headers={"X-Demo-User-Id": "2"})
    admin = client.get(f"/api/tickets/{ticket.id}", headers={"X-Demo-User-Id": "7"})

    assert own.status_code == 200
    assert other.status_code == 403
    assert admin.status_code == 200
    app.dependency_overrides.clear()


def test_ticket_list_scope_differs_for_requesters_and_admin(tmp_path: Path):
    client, session = _client(tmp_path)
    ticket_a = Ticket(requester_id=1, title="Requester A ticket", description="VPN cannot connect", user_category="网络连接", urgency="中")
    ticket_b = Ticket(requester_id=2, title="Requester B ticket", description="Database timeout", user_category="数据库", urgency="高")
    session.add(ticket_a)
    session.add(ticket_b)
    session.commit()

    list_a = client.get("/api/tickets", headers={"X-Demo-User-Id": "1"})
    list_b = client.get("/api/tickets", headers={"X-Demo-User-Id": "2"})
    list_admin = client.get("/api/tickets", headers={"X-Demo-User-Id": "7"})

    assert [item["title"] for item in list_a.json()] == ["Requester A ticket"]
    assert [item["title"] for item in list_b.json()] == ["Requester B ticket"]
    assert {item["title"] for item in list_admin.json()} == {"Requester A ticket", "Requester B ticket"}
    app.dependency_overrides.clear()


def test_admin_can_access_ticket_list_and_ai_reviews(tmp_path: Path):
    client, session = _client(tmp_path)
    ticket = Ticket(requester_id=1, title="Requester A ticket", description="VPN cannot connect", user_category="网络连接", urgency="中")
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    session.add(
        AIReview(
            ticket_id=ticket.id,
            original_category="网络连接",
            original_severity="medium",
            reviewer_note="fixture review",
        )
    )
    session.commit()

    tickets = client.get("/api/tickets", headers={"X-Demo-User-Id": "7"})
    reviews = client.get("/api/ai/reviews", headers={"X-Demo-User-Id": "7"})

    assert tickets.status_code == 200
    assert reviews.status_code == 200
    assert tickets.json()[0]["title"] == "Requester A ticket"
    assert reviews.json()[0]["ticket"]["title"] == "Requester A ticket"
    app.dependency_overrides.clear()


def test_users_api_is_admin_only(tmp_path: Path):
    client, _ = _client(tmp_path)

    requester_list = client.get("/api/users", headers={"X-Demo-User-Id": "1"})
    requester_detail = client.get("/api/users/1", headers={"X-Demo-User-Id": "1"})
    admin_list = client.get("/api/users", headers={"X-Demo-User-Id": "7"})
    admin_detail = client.get("/api/users/1", headers={"X-Demo-User-Id": "7"})

    assert requester_list.status_code == 403
    assert requester_detail.status_code == 403
    assert admin_list.status_code == 200
    assert admin_detail.status_code == 200
    assert {user["id"] for user in admin_list.json()} == {1, 2, 7}
    assert admin_detail.json()["email"] == "a@example.com"
    app.dependency_overrides.clear()


def test_ticket_create_trace_and_analysis_run_api(tmp_path: Path):
    client, _ = _client(tmp_path)
    response = client.post(
        "/api/tickets",
        headers={"X-Demo-User-Id": "1"},
        data={
            "title": "VPN cannot connect",
            "description": "VPN cannot connect from home network",
            "category": "网络连接",
            "urgency": "中",
            "affected_system": "VPN",
            "contact_email": "a@example.com",
        },
    )
    assert response.status_code == 200
    body = response.json()
    runs = client.get(f"/api/tickets/{body['ticket_id']}/analysis-runs", headers={"X-Demo-User-Id": "1"})
    trace = client.get(f"/api/tickets/{body['ticket_id']}/analysis-runs/{body['run_id']}/trace", headers={"X-Demo-User-Id": "1"})

    assert body["trace_id"]
    assert runs.status_code == 200
    assert trace.status_code == 200
    assert trace.json()["stage_traces"]
    app.dependency_overrides.clear()


def test_attachment_rejects_disallowed_content(tmp_path: Path):
    client, _ = _client(tmp_path)
    created = client.post(
        "/api/tickets",
        headers={"X-Demo-User-Id": "1"},
        data={
            "title": "VPN cannot connect",
            "description": "VPN cannot connect",
            "category": "网络连接",
            "urgency": "中",
            "contact_email": "a@example.com",
        },
    )
    ticket_id = created.json()["ticket_id"]
    rejected = client.post(
        f"/api/tickets/{ticket_id}/attachments",
        headers={"X-Demo-User-Id": "1"},
        files={"file": ("evil.exe", b"\x00\x01binary", "application/octet-stream")},
    )

    assert rejected.status_code == 400
    app.dependency_overrides.clear()


def test_legacy_ai_endpoints_are_removed(tmp_path: Path):
    client, _ = _client(tmp_path)
    endpoints = [
        ("/api/ai/classify-ticket", {"title": "VPN", "description": "VPN cannot connect"}),
        ("/api/ai/suggest-resolution", {"category": "网络连接", "severity": "medium"}),
        ("/api/ai/retrieve-kb", {"query": "VPN cannot connect"}),
    ]

    for endpoint, payload in endpoints:
        response = client.post(endpoint, headers={"X-Demo-User-Id": "1"}, json=payload)
        assert response.status_code == 404
    app.dependency_overrides.clear()
