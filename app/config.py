import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "instance", "saipa_mashayekh.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", os.path.join(BASE_DIR, "instance", "uploads"))
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB per request
    ALLOWED_UPLOAD_EXTENSIONS = {
        "png", "jpg", "jpeg", "gif", "webp",
        "pdf", "doc", "docx", "xls", "xlsx", "csv", "txt", "zip",
    }

    ORG_NAME = "Saipa Mashayekh"
    ORG_CODE = "3299"
    ORG_FULL_NAME = "Saipa Mashayekh — Code 3299"

    ITEMS_PER_PAGE = 20

    WTF_CSRF_TIME_LIMIT = None


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    UPLOAD_FOLDER = "/tmp/saipa_mashayekh_test_uploads"
