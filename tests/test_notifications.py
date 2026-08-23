from tests.conftest import login


def test_notification_created_on_new_ticket(app, client):
    login(client, "employee@test.local")
    client.post(
        "/tickets/create",
        data={
            "title": "Need IT help",
            "description": "Details here.",
            "category_id": "1",
            "priority": "medium",
            "recipient_type": "department",
            "recipient_department_id": "1",
        },
        content_type="multipart/form-data",
    )
    client.post("/auth/logout")

    login(client, "itmanager@test.local", password="Passw0rd!")
    resp = client.get("/api/notifications/summary")
    data = resp.get_json()
    assert data["unread_count"] >= 1
    assert any(item["title"].startswith("New request") for item in data["items"])


def test_mark_all_read_clears_unread_count(client):
    login(client, "employee@test.local")
    client.post(
        "/tickets/create",
        data={
            "title": "Need IT help",
            "description": "Details here.",
            "category_id": "1",
            "priority": "medium",
            "recipient_type": "department",
            "recipient_department_id": "1",
        },
        content_type="multipart/form-data",
    )
    client.post("/auth/logout")

    login(client, "itmanager@test.local", password="Passw0rd!")
    client.post("/notifications/mark-all-read")
    resp = client.get("/api/notifications/summary")
    assert resp.get_json()["unread_count"] == 0


def test_reply_notifies_ticket_creator(app, client):
    login(client, "employee@test.local")
    client.post(
        "/tickets/create",
        data={
            "title": "Need IT help",
            "description": "Details here.",
            "category_id": "1",
            "priority": "medium",
            "recipient_type": "department",
            "recipient_department_id": "1",
        },
        content_type="multipart/form-data",
    )
    client.post("/auth/logout")

    login(client, "itmanager@test.local", password="Passw0rd!")
    client.post("/tickets/1/reply", data={"body": "On it."})
    client.post("/auth/logout")

    login(client, "employee@test.local")
    resp = client.get("/api/notifications/summary")
    data = resp.get_json()
    assert any("New reply" in item["title"] for item in data["items"])


def test_notification_requires_ownership_to_open(app, client):
    login(client, "employee@test.local")
    client.post(
        "/tickets/create",
        data={
            "title": "Need IT help",
            "description": "Details here.",
            "category_id": "1",
            "priority": "medium",
            "recipient_type": "department",
            "recipient_department_id": "1",
        },
        content_type="multipart/form-data",
    )
    client.post("/auth/logout")

    from app.models import Notification

    with app.app_context():
        notif = Notification.query.first()
        notif_id = notif.id

    # A different user shouldn't be able to mark someone else's notification read via this route.
    login(client, "employee2@test.local")
    client.get(f"/notifications/{notif_id}/open")

    with app.app_context():
        assert Notification.query.get(notif_id).is_read is False
