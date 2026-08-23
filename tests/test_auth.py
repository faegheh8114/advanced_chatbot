from tests.conftest import login


def test_login_success(client):
    resp = login(client, "employee@test.local")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/dashboard/"


def test_login_wrong_password(client):
    resp = login(client, "employee@test.local", password="wrong-password")
    assert resp.status_code == 401
    assert b"Incorrect email or password" in resp.data


def test_login_unknown_email(client):
    resp = login(client, "nobody@test.local")
    assert resp.status_code == 401


def test_password_is_hashed_not_plaintext(app):
    from app.models import User

    with app.app_context():
        user = User.query.filter_by(email="employee@test.local").first()
        assert user.password_hash != "Passw0rd!"
        assert user.check_password("Passw0rd!")
        assert not user.check_password("wrong")


def test_protected_route_requires_login(client):
    resp = client.get("/dashboard/")
    assert resp.status_code in (302, 401)


def test_logout(client):
    login(client, "employee@test.local")
    resp = client.post("/auth/logout")
    assert resp.status_code == 302
    resp = client.get("/dashboard/")
    assert resp.status_code in (302, 401)


def test_deactivated_user_cannot_login(app, client):
    from app.extensions import db
    from app.models import User

    with app.app_context():
        user = User.query.filter_by(email="employee@test.local").first()
        user.is_active = False
        db.session.commit()

    resp = login(client, "employee@test.local")
    assert resp.status_code == 403
