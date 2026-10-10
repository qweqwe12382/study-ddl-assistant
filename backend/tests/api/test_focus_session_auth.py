"""Focus recording keeps cookie/CSRF checks and independent account workspaces."""

from test_auth import auth_client, _csrf_headers  # noqa: F401


def test_focus_records_cannot_cross_accounts_with_reused_numeric_ids(auth_client):
    client = auth_client
    assert client.post("/api/tasks/1/focus-sessions", json={"minutes": 25, "idempotency_key": "session"}).status_code == 401

    def register(email):
        response = client.post("/api/auth/register", json={
            "email": email, "display_name": "隔离测试", "password": "private2026",
        })
        assert response.status_code == 201
        task = client.post("/api/tasks", json={"name": "自己的专注任务"}, headers=_csrf_headers(client))
        assert task.status_code == 201
        return task.json()

    first = register("focus-first@example.com")
    first_tag = f'"{first["navigation_key"]}:{first["revision"]}"'
    assert client.post(f'/api/tasks/{first["id"]}/focus-sessions', json={
        "minutes": 25, "idempotency_key": "private-focus-session",
    }, headers={"If-Match": first_tag}).status_code == 403
    first_saved = client.post(f'/api/tasks/{first["id"]}/focus-sessions', json={
        "minutes": 25, "idempotency_key": "private-focus-session",
    }, headers={**_csrf_headers(client), "If-Match": first_tag})
    assert first_saved.status_code == 200
    assert client.post("/api/auth/logout", headers=_csrf_headers(client)).status_code == 204

    second = register("focus-second@example.com")
    assert second["id"] == first["id"]
    assert second["navigation_key"] != first["navigation_key"]
    url = f'/api/tasks/{second["id"]}/focus-sessions'
    assert client.post(url, json={"minutes": 25, "idempotency_key": "private-focus-session"},
                       headers={**_csrf_headers(client), "If-Match": first_tag}).status_code == 409
    second_saved = client.post(url, json={"minutes": 30, "idempotency_key": "private-focus-session"},
                               headers={**_csrf_headers(client), "If-Match": f'"{second["navigation_key"]}:{second["revision"]}"'})
    assert second_saved.status_code == 200
    assert second_saved.json()["actual_minutes"] == 30
    assert client.post("/api/auth/logout", headers=_csrf_headers(client)).status_code == 204
    assert client.post("/api/auth/login", json={"email": "focus-first@example.com", "password": "private2026"}).status_code == 200
    assert client.get(f'/api/tasks/{first["id"]}').json()["actual_minutes"] == 25
