import pytest

from clinicfix.app import create_app
from clinicfix.models import MaintenanceStaff, User, db


@pytest.fixture()
def client(tmp_path):
    database_file = tmp_path / "test.db"
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_file}",
        }
    )
    with app.test_client() as test_client:
        yield test_client
    with app.app_context():
        db.drop_all()


def login_headers(client):
    with client.application.app_context():
        user = User(
            name="API Test Technician",
            email="api-test@example.com",
            role="technician",
        )
        user.set_password("TestPass123")
        db.session.add(user)
        db.session.commit()

    response = client.post(
        "/api/auth/login",
        json={"email": "api-test@example.com", "password": "TestPass123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json['access_token']}"}


def create_equipment(client, headers, **overrides):
    payload = {
        "name": "Portable X-ray",
        "category": "Imaging",
        "location": "Room 3",
        **overrides,
    }
    return client.post("/api/equipment", json=payload, headers=headers)


def test_health_check(client):
    response = client.get("/api/healthz")
    assert response.status_code == 200
    assert response.json["status"] == "ok"


def test_crud_requires_authentication(client):
    response = client.get("/api/equipment")
    assert response.status_code == 401


def test_equipment_crud(client):
    headers = login_headers(client)
    created = create_equipment(client, headers, serial_number="XR-100")
    assert created.status_code == 201
    equipment_id = created.json["id"]

    assert client.get("/api/equipment", headers=headers).json[0]["name"] == "Portable X-ray"
    assert client.get(f"/api/equipment/{equipment_id}", headers=headers).status_code == 200

    updated = client.patch(
        f"/api/equipment/{equipment_id}", json={"location": "Room 5"}, headers=headers
    )
    assert updated.status_code == 200
    assert updated.json["location"] == "Room 5"

    assert client.delete(f"/api/equipment/{equipment_id}", headers=headers).status_code == 204
    assert client.get(f"/api/equipment/{equipment_id}", headers=headers).status_code == 404


def test_staff_crud(client):
    headers = login_headers(client)
    created = client.post(
        "/api/maintenance-staff",
        json={"name": "Ada Tech", "email": "ADA@example.com"},
        headers=headers,
    )
    assert created.status_code == 201
    staff_id = created.json["id"]
    assert created.json["email"] == "ada@example.com"

    assert client.get("/api/maintenance-staff", headers=headers).status_code == 200
    assert client.get(f"/api/maintenance-staff/{staff_id}", headers=headers).status_code == 200
    assert (
        client.patch(
            f"/api/maintenance-staff/{staff_id}",
            json={"is_active": False},
            headers=headers,
        ).json["is_active"]
        is False
    )
    assert client.delete(f"/api/maintenance-staff/{staff_id}", headers=headers).status_code == 204


def test_maintenance_request_crud_and_equipment_delete_guard(client):
    headers = login_headers(client)
    equipment_id = create_equipment(client, headers).json["id"]
    staff = client.post(
        "/api/maintenance-staff",
        json={"name": "Sam Service", "email": "sam@example.com"},
        headers=headers,
    )
    staff_id = staff.json["id"]

    created = client.post(
        "/api/maintenance-requests",
        json={
            "equipment_id": equipment_id,
            "assigned_staff_id": staff_id,
            "description": "The power button is stuck.",
            "priority": "high",
        },
        headers=headers,
    )
    assert created.status_code == 201
    request_id = created.json["id"]
    assert created.json["status"] == "open"
    assert client.delete(f"/api/equipment/{equipment_id}", headers=headers).status_code == 409

    assert client.get("/api/maintenance-requests", headers=headers).status_code == 200
    assert client.get(f"/api/maintenance-requests/{request_id}", headers=headers).status_code == 200
    updated = client.patch(
        f"/api/maintenance-requests/{request_id}",
        json={"status": "completed"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json["status"] == "completed"

    assert client.delete(f"/api/maintenance-requests/{request_id}", headers=headers).status_code == 204
    assert client.delete(f"/api/equipment/{equipment_id}", headers=headers).status_code == 204


def test_validation_and_conflicts(client):
    headers = login_headers(client)
    invalid = client.post(
        "/api/equipment",
        json={"name": "   ", "category": 12},
        headers=headers,
    )
    assert invalid.status_code == 400
    assert "errors" in invalid.json

    assert create_equipment(client, headers, serial_number="DUPLICATE").status_code == 201
    assert create_equipment(client, headers, serial_number="DUPLICATE").status_code == 409

    missing_reference = client.post(
        "/api/maintenance-requests",
        json={"equipment_id": 999, "description": "Needs inspection"},
        headers=headers,
    )
    assert missing_reference.status_code == 404


def test_json_body_is_required(client):
    headers = login_headers(client)
    response = client.post(
        "/api/equipment",
        data='{"name":"Monitor"}',
        content_type="text/plain",
        headers=headers,
    )
    assert response.status_code == 400


def test_login_success(client):
    with client.application.app_context():
        user = User(
            name="Test Technician",
            email="technician@example.com",
            role="technician",
        )
        user.set_password("TestPass123")
        db.session.add(user)
        db.session.commit()

    response = client.post(
        "/api/auth/login",
        json={"email": "technician@example.com", "password": "TestPass123"},
    )
    assert response.status_code == 200
    assert response.json["token_type"] == "Bearer"
    assert isinstance(response.json["access_token"], str)
    assert response.json["access_token"]


def test_login_wrong_password(client):
    with client.application.app_context():
        user = User(name="Test Technician", email="technician@example.com")
        user.set_password("TestPass123")
        db.session.add(user)
        db.session.commit()

    response = client.post(
        "/api/auth/login",
        json={"email": "technician@example.com", "password": "WrongPass123"},
    )
    assert response.status_code == 401
    assert response.json["error"] == "Invalid email or password."


def test_login_inactive_user(client):
    with client.application.app_context():
        user = User(
            name="Inactive Technician",
            email="inactive@example.com",
            is_active=False,
        )
        user.set_password("TestPass123")
        db.session.add(user)
        db.session.commit()

    response = client.post(
        "/api/auth/login",
        json={"email": "inactive@example.com", "password": "TestPass123"},
    )
    assert response.status_code == 401
    assert response.json["error"] == "Invalid email or password."


def test_login_requires_email_and_password(client):
    email_only_response = client.post(
        "/api/auth/login",
        json={"email": "technician@example.com"},
    )
    empty_body_response = client.post("/api/auth/login", json={})

    assert email_only_response.status_code == 400
    assert "error" in email_only_response.json
    assert empty_body_response.status_code == 400
    assert "error" in empty_body_response.json


def test_user_can_link_to_maintenance_staff(client):
    with client.application.app_context():
        staff = MaintenanceStaff(
            name="Assigned Technician",
            email="staff-record@example.com",
        )
        user = User(
            name="Technician Account",
            email="login-account@example.com",
            role="technician",
            maintenance_staff=staff,
        )
        user.set_password("TestPass123")
        admin = User(
            name="Administrator",
            email="admin-account@example.com",
            role="admin",
        )
        admin.set_password("AdminPass123")
        db.session.add_all([staff, user, admin])
        db.session.commit()

        assert user.maintenance_staff_id == staff.id
        assert user.maintenance_staff is staff
        assert staff.user is user
        assert admin.maintenance_staff_id is None
