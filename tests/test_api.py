import pytest

from backend.app import create_app


def register(client, email="owner@example.com", name="Workspace Owner", password="StrongPass123"):
    return client.post("/api/auth/register", json={"name": name, "email": email, "password": password})


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json == {"status": "ok"}


def test_production_requires_a_persistent_secret(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("FLASK_DEBUG", "false")
    with pytest.raises(RuntimeError, match="persistent random value"):
        create_app()


def test_frontend_cors_preflight_is_allowed(client):
    response = client.options("/api/auth/login", headers={
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"


def test_registration_hashes_password_and_login_works(client, app):
    response = register(client)
    assert response.status_code == 201
    assert response.json["user"]["email"] == "owner@example.com"
    assert "password" not in response.json

    from backend.app import User

    with app.app_context():
        user = User.query.filter_by(email="owner@example.com").first()
    assert user.password_hash != "StrongPass123"

    login = client.post("/api/auth/login", json={"email": "OWNER@example.com", "password": "StrongPass123"})
    assert login.status_code == 200
    assert login.json["user"]["id"] == response.json["user"]["id"]


def test_auth_validation_duplicate_email_and_invalid_login(client):
    assert client.post("/api/auth/register", json={"name": "A", "email": "bad", "password": "123"}).status_code == 400
    assert register(client).status_code == 201
    assert register(client).status_code == 409
    assert client.post("/api/auth/login", json={"email": "owner@example.com", "password": "wrong-pass"}).status_code == 401
    assert client.get("/api/tasks").status_code == 401


def test_task_crud_search_filter_and_access_control(client, auth_headers):
    created = client.post("/api/tasks", headers=auth_headers, json={
        "title": "Check checkout",
        "description": "Exercise the purchase path",
        "priority": "high",
        "due_date": "2026-12-01",
    })
    assert created.status_code == 201
    task = created.json["task"]
    assert task["status"] == "todo"
    task_id = task["id"]

    assert client.get("/api/tasks?search=purchase", headers=auth_headers).json["tasks"][0]["id"] == task_id
    assert client.get("/api/tasks?priority=low", headers=auth_headers).json["tasks"] == []

    updated = client.patch(f"/api/tasks/{task_id}", headers=auth_headers, json={"status": "in_progress", "priority": "medium"})
    assert updated.status_code == 200
    assert updated.json["task"]["status"] == "in_progress"
    assert client.get("/api/tasks?status=not-a-status", headers=auth_headers).status_code == 400
    assert client.patch(f"/api/tasks/{task_id}", headers=auth_headers, json={"status": "unknown"}).status_code == 400
    assert client.patch(f"/api/tasks/{task_id}", headers=auth_headers, json={}).status_code == 400

    second_account = register(client, email="second@example.com", name="Other User")
    second_headers = {"Authorization": f"Bearer {second_account.json['token']}"}
    assert client.get("/api/tasks", headers=second_headers).json["tasks"] == []
    assert client.get(f"/api/tasks/{task_id}", headers=second_headers).status_code == 404
    assert client.delete(f"/api/tasks/{task_id}", headers=second_headers).status_code == 404

    assert client.delete(f"/api/tasks/{task_id}", headers=auth_headers).status_code == 200
    assert client.delete(f"/api/tasks/{task_id}", headers=auth_headers).status_code == 404


def test_invalid_task_payloads_are_rejected(client, auth_headers):
    assert client.post("/api/tasks", headers=auth_headers, json={"title": " "}).status_code == 400
    assert client.post("/api/tasks", headers=auth_headers, data="not json", content_type="application/json").status_code == 400
