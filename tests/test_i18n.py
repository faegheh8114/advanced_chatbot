from tests.conftest import login


def test_default_locale_is_english(client):
    resp = client.get("/auth/login")
    assert b'dir="ltr"' in resp.data
    assert b'lang="en"' in resp.data


def test_switch_to_persian_sets_rtl(client):
    client.post("/set-language/fa")
    resp = client.get("/auth/login")
    assert b'dir="rtl"' in resp.data
    assert b'lang="fa"' in resp.data


def test_invalid_locale_is_ignored(client):
    client.post("/set-language/xx")
    resp = client.get("/auth/login")
    assert b'dir="ltr"' in resp.data


def test_locale_choice_persists_across_login(client):
    # A language picked anonymously (e.g. on the login page) should still be
    # in effect right after signing in, via the session — not yet written to
    # the account, since there was no authenticated user to attach it to.
    client.post("/set-language/fa")
    login(client, "employee@test.local")
    resp = client.get("/dashboard/")
    assert b'dir="rtl"' in resp.data


def test_switching_language_while_logged_in_saves_to_account(app, client):
    login(client, "employee@test.local")
    client.post("/set-language/fa")

    from app.models import User

    with app.app_context():
        user = User.query.filter_by(email="employee@test.local").first()
        assert user.language == "fa"


def test_authenticated_user_saved_preference_used_without_session_override(app, client):
    from app.extensions import db
    from app.models import User

    with app.app_context():
        user = User.query.filter_by(email="employee@test.local").first()
        user.language = "fa"
        db.session.commit()

    login(client, "employee@test.local")
    resp = client.get("/dashboard/")
    assert b'dir="rtl"' in resp.data


def test_status_and_priority_labels_localized(client):
    client.post("/set-language/fa")
    login(client, "employee@test.local")
    resp = client.get("/tickets/create")
    assert "اولویت".encode() in resp.data
