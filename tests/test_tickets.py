import io

from tests.conftest import login


def _create_ticket(client, **overrides):
    data = {
        "title": "Printer is broken",
        "description": "The printer on the 2nd floor is jammed.",
        "category_id": "1",
        "priority": "medium",
        "recipient_type": "department",
        "recipient_department_id": "1",  # IT
    }
    data.update(overrides)
    return client.post("/tickets/create", data=data, content_type="multipart/form-data")


def test_create_ticket_to_department(app, client):
    login(client, "employee@test.local")
    resp = _create_ticket(client)
    assert resp.status_code == 302

    from app.models import Ticket, TicketStatus

    with app.app_context():
        ticket = Ticket.query.first()
        assert ticket.title == "Printer is broken"
        assert ticket.status == TicketStatus.OPEN
        assert ticket.department is not None
        assert ticket.department.name == "IT"
        # Auto-assigned to the department manager.
        assert ticket.assignee is not None


def test_create_ticket_with_attachment(app, client):
    login(client, "employee@test.local")
    resp = client.post(
        "/tickets/create",
        data={
            "title": "Need a new monitor",
            "description": "My monitor flickers constantly.",
            "category_id": "1",
            "priority": "low",
            "recipient_type": "department",
            "recipient_department_id": "1",
            "attachments": (io.BytesIO(b"fake image bytes"), "photo.png"),
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 302

    from app.models import TicketAttachment

    with app.app_context():
        attachment = TicketAttachment.query.first()
        assert attachment is not None
        assert attachment.original_filename == "photo.png"


def test_ticket_creator_can_view_own_ticket(client):
    login(client, "employee@test.local")
    _create_ticket(client)
    resp = client.get("/tickets/1")
    assert resp.status_code == 200
    assert b"Printer is broken" in resp.data


def test_unrelated_employee_cannot_view_ticket(client):
    login(client, "employee@test.local")
    _create_ticket(client, recipient_type="user", recipient_user_id="1")  # sent to admin, not IT dept
    client.post("/auth/logout")

    login(client, "employee2@test.local")  # different department, not creator/recipient/assignee
    resp = client.get("/tickets/1")
    assert resp.status_code == 403


def test_department_member_can_view_department_ticket(client):
    login(client, "employee@test.local")
    _create_ticket(client)  # sent to IT department
    client.post("/auth/logout")

    login(client, "itmanager@test.local")
    resp = client.get("/tickets/1")
    assert resp.status_code == 200


def test_only_manager_or_assignee_can_change_status(client):
    login(client, "employee@test.local")
    _create_ticket(client)

    # Creator (not assignee/manager) cannot change status.
    resp = client.post("/tickets/1/status", data={"status": "resolved"})
    assert resp.status_code == 403

    client.post("/auth/logout")
    login(client, "itmanager@test.local")
    resp = client.post("/tickets/1/status", data={"status": "resolved"})
    assert resp.status_code == 302


def test_status_change_persists_and_logs_activity(app, client):
    login(client, "employee@test.local")
    _create_ticket(client)
    client.post("/auth/logout")
    login(client, "itmanager@test.local")
    client.post("/tickets/1/status", data={"status": "resolved"})

    from app.models import Ticket, ActivityLog, TicketStatus

    with app.app_context():
        ticket = Ticket.query.get(1)
        assert ticket.status == TicketStatus.RESOLVED
        assert ticket.resolved_at is not None
        assert ActivityLog.query.filter_by(action="status_changed").count() == 1


def test_reply_creates_message_and_notifies_creator(app, client):
    login(client, "employee@test.local")
    _create_ticket(client)
    client.post("/auth/logout")

    login(client, "itmanager@test.local")
    resp = client.post("/tickets/1/reply", data={"body": "Looking into it now."})
    assert resp.status_code == 302

    from app.models import TicketMessage, Notification

    with app.app_context():
        assert TicketMessage.query.filter_by(body="Looking into it now.").count() == 1
        assert Notification.query.count() >= 1


def test_assign_ticket_updates_assignee(app, client):
    login(client, "employee@test.local")
    _create_ticket(client)
    client.post("/auth/logout")

    login(client, "itmanager@test.local")

    from app.models import User

    with app.app_context():
        it_manager = User.query.filter_by(email="itmanager@test.local").first()
        it_manager_id = it_manager.id

    resp = client.post("/tickets/1/assign", data={"assignee_id": str(it_manager_id)})
    assert resp.status_code == 302

    from app.models import Ticket

    with app.app_context():
        ticket = Ticket.query.get(1)
        assert ticket.assignee_id == it_manager_id


def test_internal_note_hidden_from_non_staff(client):
    login(client, "employee@test.local")
    _create_ticket(client)
    client.post("/auth/logout")

    login(client, "itmanager@test.local")
    client.post("/tickets/1/reply", data={"body": "Internal note text", "is_internal_note": "1"})
    client.post("/auth/logout")

    login(client, "employee@test.local")
    resp = client.get("/tickets/1")
    assert b"Internal note text" not in resp.data


def test_download_attachment_requires_access(client):
    login(client, "employee@test.local")
    client.post(
        "/tickets/create",
        data={
            "title": "Confidential request",
            "description": "Sensitive.",
            "category_id": "1",
            "priority": "low",
            "recipient_type": "user",
            "recipient_user_id": "1",
            "attachments": (io.BytesIO(b"secret file"), "secret.txt"),
        },
        content_type="multipart/form-data",
    )
    client.post("/auth/logout")

    login(client, "employee2@test.local")
    resp = client.get("/tickets/attachments/1")
    assert resp.status_code == 403


def test_upload_rejects_disallowed_extension(app, client):
    login(client, "employee@test.local")
    resp = client.post(
        "/tickets/create",
        data={
            "title": "Suspicious upload",
            "description": "Testing file validation.",
            "category_id": "1",
            "priority": "low",
            "recipient_type": "department",
            "recipient_department_id": "1",
            "attachments": (io.BytesIO(b"#!/bin/sh\necho hi"), "script.sh"),
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 302

    from app.models import TicketAttachment

    # Disallowed extension: ticket is still created, but the attachment must be rejected.
    with app.app_context():
        assert TicketAttachment.query.count() == 0
