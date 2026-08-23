import shutil

import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import User, Department, Category, Role


@pytest.fixture()
def app():
    application = create_app(TestConfig)
    with application.app_context():
        db.create_all()

        it_dept = Department(name="IT", description="Tech support")
        sales_dept = Department(name="Sales", description="Sales team")
        db.session.add_all([it_dept, sales_dept])
        db.session.flush()

        db.session.add(Category(name="IT Support"))
        db.session.add(Category(name="Sales"))
        db.session.flush()

        admin = User(name="Admin User", email="admin@test.local", role=Role.SUPER_ADMIN, department_id=it_dept.id)
        admin.set_password("Admin@12345")

        it_manager = User(name="IT Manager", email="itmanager@test.local", role=Role.MANAGER, department_id=it_dept.id)
        it_manager.set_password("Passw0rd!")

        employee = User(name="Employee One", email="employee@test.local", role=Role.EMPLOYEE, department_id=sales_dept.id)
        employee.set_password("Passw0rd!")

        other_employee = User(name="Employee Two", email="employee2@test.local", role=Role.EMPLOYEE, department_id=sales_dept.id)
        other_employee.set_password("Passw0rd!")

        db.session.add_all([admin, it_manager, employee, other_employee])
        db.session.flush()

        it_dept.manager_id = it_manager.id
        db.session.commit()

        yield application

        db.session.remove()
        db.drop_all()
    shutil.rmtree(TestConfig.UPLOAD_FOLDER, ignore_errors=True)


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, email, password="Passw0rd!"):
    return client.post("/auth/login", data={"email": email, "password": password})
