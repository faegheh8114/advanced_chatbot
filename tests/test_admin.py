from tests.conftest import login


def test_employee_cannot_access_admin_dashboard(client):
    login(client, "employee@test.local")
    resp = client.get("/admin/")
    assert resp.status_code == 403


def test_manager_cannot_access_admin_dashboard(client):
    login(client, "itmanager@test.local", password="Passw0rd!")
    resp = client.get("/admin/")
    assert resp.status_code == 403


def test_anonymous_redirected_from_admin(client):
    resp = client.get("/admin/")
    assert resp.status_code in (302, 401)


def test_super_admin_can_access_admin_dashboard(client):
    login(client, "admin@test.local", password="Admin@12345")
    resp = client.get("/admin/")
    assert resp.status_code == 200
    assert b"Management Dashboard" in resp.data


def test_admin_can_create_user(app, client):
    login(client, "admin@test.local", password="Admin@12345")
    resp = client.post(
        "/admin/users/create",
        data={
            "name": "Brand New Hire",
            "email": "newhire@test.local",
            "role": "employee",
            "department_id": "2",
            "password": "SecurePass123",
        },
    )
    assert resp.status_code == 302

    from app.models import User

    with app.app_context():
        user = User.query.filter_by(email="newhire@test.local").first()
        assert user is not None
        assert user.role == "employee"
        assert user.check_password("SecurePass123")


def test_admin_cannot_create_duplicate_email(client):
    login(client, "admin@test.local", password="Admin@12345")
    resp = client.post(
        "/admin/users/create",
        data={
            "name": "Duplicate",
            "email": "employee@test.local",
            "role": "employee",
            "department_id": "2",
            "password": "SecurePass123",
        },
    )
    assert resp.status_code == 200
    assert b"already exists" in resp.data


def test_admin_can_deactivate_and_reactivate_user(app, client):
    login(client, "admin@test.local", password="Admin@12345")

    from app.models import User

    with app.app_context():
        target = User.query.filter_by(email="employee@test.local").first()
        target_id = target.id

    resp = client.post(f"/admin/users/{target_id}/toggle-active")
    assert resp.status_code == 302
    with app.app_context():
        assert User.query.get(target_id).is_active is False

    client.post(f"/admin/users/{target_id}/toggle-active")
    with app.app_context():
        assert User.query.get(target_id).is_active is True


def test_admin_cannot_delete_self(app, client):
    login(client, "admin@test.local", password="Admin@12345")

    from app.models import User

    with app.app_context():
        admin = User.query.filter_by(email="admin@test.local").first()
        admin_id = admin.id

    client.post(f"/admin/users/{admin_id}/delete")

    with app.app_context():
        assert User.query.get(admin_id) is not None


def test_admin_can_create_department(app, client):
    login(client, "admin@test.local", password="Admin@12345")
    resp = client.post("/admin/departments/create", data={"name": "Legal", "description": "Contracts", "manager_id": ""})
    assert resp.status_code == 302

    from app.models import Department

    with app.app_context():
        assert Department.query.filter_by(name="Legal").first() is not None


def test_admin_can_toggle_department_active(app, client):
    login(client, "admin@test.local", password="Admin@12345")

    from app.models import Department

    with app.app_context():
        dept = Department.query.filter_by(name="Sales").first()
        dept_id = dept.id
        assert dept.is_active is True

    client.post(f"/admin/departments/{dept_id}/toggle-active")
    with app.app_context():
        assert Department.query.get(dept_id).is_active is False


def test_admin_can_create_category(app, client):
    login(client, "admin@test.local", password="Admin@12345")
    resp = client.post("/admin/categories", data={"name": "Facilities"})
    assert resp.status_code == 302

    from app.models import Category

    with app.app_context():
        assert Category.query.filter_by(name="Facilities").first() is not None


def test_activity_log_records_admin_actions(app, client):
    login(client, "admin@test.local", password="Admin@12345")
    client.post("/admin/categories", data={"name": "Facilities"})

    from app.models import ActivityLog

    with app.app_context():
        assert ActivityLog.query.filter_by(action="category_created").count() == 1
