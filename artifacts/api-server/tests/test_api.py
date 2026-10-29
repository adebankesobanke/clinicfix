import pytest

from clinicfix.app import create_app
from clinicfix.models import User, db


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


def create_equipment(client, **overrides):
    payload = {
        "name": "Portable X-ray",
        "category": "Imaging",
        "location": "Room 3",
        **overrides,
    }
    return client.post("/api/equipment", json=payload)


def test_health_check(client):
    response = client.get("/api/healthz")
    assert response.status_code == 200
    assert response.json["status"] == "ok"


def test_equipment_crud(client):
    created = create_equipment(client, serial_number="XR-100")
    assert created.status_code == 201
    equipment_id = created.json["id"]

    assert client.get("/api/equipment").json[0]["name"] == "Portable X-ray"
    assert client.get(f"/api/equipment/{equipment_id}").status_code == 200

    updated = client.patch(
        f"/api/equipment/{equipment_id}", json={"location": "Room 5"}
    )
    assert updated.status_code == 200
    assert updated.json["location"] == "Room 5"

    assert client.delete(f"/api/equipment/{equipment_id}").status_code == 204
    assert client.get(f"/api/equipment/{equipment_id}").status_code == 404


def test_staff_crud(client):
    created = client.post(
        "/api/maintenance-staff",
        json={"name": "Ada Tech", "email": "ADA@example.com"},
    )
    assert created.status_code == 201
    staff_id = created.json["id"]
    assert created.json["email"] == "ada@example.com"

    assert client.get("/api/maintenance-staff").status_code == 200
    assert client.get(f"/api/maintenance-staff/{staff_id}").status_code == 200
    assert (
        client.patch(
            f"/api/maintenance-staff/{staff_id}", json={"is_active": False}
        ).json["is_active"]
        is False
    )
    assert client.delete(f"/api/maintenance-staff/{staff_id}").status_code == 204


def test_maintenance_request_crud_and_equipment_delete_guard(client):
    equipment_id = create_equipment(client).json["id"]
    staff = client.post(
        "/api/maintenance-staff",
        json={"name": "Sam Service", "email": "sam@example.com"},
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
    )
    assert created.status_code == 201
    request_id = created.json["id"]
    assert created.json["status"] == "open"
    assert client.delete(f"/api/equipment/{equipment_id}").status_code == 409

    assert client.get("/api/maintenance-requests").status_code == 200
    assert client.get(f"/api/maintenance-requests/{request_id}").status_code == 200
    updated = client.patch(
        f"/api/maintenance-requests/{request_id}", json={"status": "completed"}
    )
    assert updated.status_code == 200
    assert updated.json["status"] == "completed"

    assert client.delete(f"/api/maintenance-requests/{request_id}").status_code == 204
    assert client.delete(f"/api/equipment/{equipment_id}").status_code == 204


def test_validation_and_conflicts(client):
    invalid = client.post("/api/equipment", json={"name": "   ", "category": 12})
    assert invalid.status_code == 400
    assert "errors" in invalid.json

    assert create_equipment(client, serial_number="DUPLICATE").status_code == 201
    assert create_equipment(client, serial_number="DUPLICATE").status_code == 409

    missing_reference = client.post(
        "/api/maintenance-requests",
        json={"equipment_id": 999, "description": "Needs inspection"},
    )
    assert missing_reference.status_code == 404


def test_json_body_is_required(client):
    response = client.post(
        "/api/equipment",
        data='{"name":"Monitor"}',
        content_type="text/plain",
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
