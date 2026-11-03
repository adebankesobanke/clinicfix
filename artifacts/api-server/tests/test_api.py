
import pytest

from clinicfix.app import create_app
from clinicfix.models import (
    Equipment,
    MaintenanceRequest,
    MaintenanceStaff,
    User,
    db,
)


@pytest.fixture()
def client(tmp_path):
    database_file = tmp_path / "test.db"

    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_file}",
        }
    )

    # Create tables only in the temporary test database.
    with app.app_context():
        db.create_all()

    with app.test_client() as test_client:
        yield test_client

    # Clean up the temporary test database.
    with app.app_context():
        db.session.remove()
        db.drop_all()


def create_user(client, role="technician", is_active=True):
    """Create a test user and return the user ID."""

    with client.application.app_context():
        user = User(
            name="API Test User",
            email=f"{role}-api-test@example.com",
            role=role,
            is_active=is_active,
            must_change_password=False,
        )

        user.set_password("TestPass123")
        db.session.add(user)
        db.session.commit()

        return user.id


def login_headers(client, role="technician"):
    """Log in a test user and return its authorization header."""

    create_user(client, role=role)

    response = client.post(
        "/api/auth/login",
        json={
            "email": f"{role}-api-test@example.com",
            "password": "TestPass123",
        },
    )

    assert response.status_code == 200

    return {
        "Authorization": f"Bearer {response.json['access_token']}"
    }


def create_equipment(client, headers):
    """Create equipment using an administrator account."""

    return client.post(
        "/api/equipment",
        headers=headers,
        json={
            "name": "Portable X-ray",
            "category": "Imaging",
            "location": "Room 3",
        },
    )


def test_health_check(client):
    response = client.get("/api/healthz")

    assert response.status_code == 200
    assert response.json["status"] == "ok"


def test_resource_access_requires_authentication(client):
    response = client.get("/api/equipment")

    assert response.status_code == 401


def test_technician_cannot_create_equipment(client):
    headers = login_headers(client, "technician")

    response = client.post(
        "/api/equipment",
        headers=headers,
        json={
            "name": "Portable X-ray",
            "category": "Imaging",
            "location": "Room 3",
        },
    )

    assert response.status_code == 403


def test_technician_cannot_update_equipment(client):
    admin_headers = login_headers(client, "admin")
    technician_headers = login_headers(client, "technician")

    created = create_equipment(client, admin_headers)
    assert created.status_code == 201

    equipment_id = created.json["id"]

    response = client.patch(
        f"/api/equipment/{equipment_id}",
        headers=technician_headers,
        json={"location": "Room 5"},
    )

    assert response.status_code == 403


def test_technician_cannot_delete_equipment(client):
    admin_headers = login_headers(client, "admin")
    technician_headers = login_headers(client, "technician")

    created = create_equipment(client, admin_headers)
    assert created.status_code == 201

    equipment_id = created.json["id"]

    response = client.delete(
        f"/api/equipment/{equipment_id}",
        headers=technician_headers,
    )

    assert response.status_code == 403


def test_equipment_crud(client):
    headers = login_headers(client, "admin")

    # Create equipment.
    created = create_equipment(client, headers)

    assert created.status_code == 201
    assert created.json["name"] == "Portable X-ray"

    equipment_id = created.json["id"]

    # Retrieve all equipment.
    listed = client.get(
        "/api/equipment",
        headers=headers,
    )

    assert listed.status_code == 200
    assert len(listed.json) == 1

    # Retrieve one equipment record.
    retrieved = client.get(
        f"/api/equipment/{equipment_id}",
        headers=headers,
    )

    assert retrieved.status_code == 200
    assert retrieved.json["id"] == equipment_id

    # Update equipment.
    updated = client.patch(
        f"/api/equipment/{equipment_id}",
        headers=headers,
        json={"location": "Room 5"},
    )

    assert updated.status_code == 200
    assert updated.json["location"] == "Room 5"

    # Delete equipment.
    deleted = client.delete(
        f"/api/equipment/{equipment_id}",
        headers=headers,
    )

    assert deleted.status_code == 204


def test_staff_crud(client):
    headers = login_headers(client)

    # Create maintenance staff.
    created = client.post(
        "/api/maintenance-staff",
        headers=headers,
        json={
            "name": "John Technician",
            "email": "john@example.com",
        },
    )

    assert created.status_code == 201
    staff_id = created.json["id"]

    # Retrieve maintenance staff.
    retrieved = client.get(
        f"/api/maintenance-staff/{staff_id}",
        headers=headers,
    )

    assert retrieved.status_code == 200
    assert retrieved.json["name"] == "John Technician"

    # Update maintenance staff.
    updated = client.patch(
        f"/api/maintenance-staff/{staff_id}",
        headers=headers,
        json={"specialty": "Imaging equipment"},
    )

    assert updated.status_code == 200
    assert updated.json["specialty"] == "Imaging equipment"

    # Delete maintenance staff.
    deleted = client.delete(
        f"/api/maintenance-staff/{staff_id}",
        headers=headers,
    )

    assert deleted.status_code == 204


def test_maintenance_request_crud_and_equipment_delete_guard(client):
    headers = login_headers(client, "technician")
    admin_headers = login_headers(client, "admin")

    equipment_response = create_equipment(client, admin_headers)
    assert equipment_response.status_code == 201

    equipment_id = equipment_response.json["id"]

    staff_response = client.post(
        "/api/maintenance-staff",
        headers=headers,
        json={
            "name": "Jane Technician",
            "email": "jane@example.com",
        },
    )

    assert staff_response.status_code == 201
    staff_id = staff_response.json["id"]

    # Create a maintenance request.
    created = client.post(
        "/api/maintenance-requests",
        headers=headers,
        json={
            "equipment_id": equipment_id,
            "assigned_staff_id": staff_id,
            "description": "Equipment is not powering on.",
            "priority": "high",
        },
    )

    assert created.status_code == 201
    request_id = created.json["id"]

    # Equipment with an existing maintenance request cannot be deleted.
    blocked_delete = client.delete(
        f"/api/equipment/{equipment_id}",
        headers=admin_headers,
    )

    assert blocked_delete.status_code == 409

    # Retrieve the maintenance request.
    retrieved = client.get(
        f"/api/maintenance-requests/{request_id}",
        headers=headers,
    )

    assert retrieved.status_code == 200
    assert retrieved.json["equipment_id"] == equipment_id

    # Update the maintenance request.
    updated = client.patch(
        f"/api/maintenance-requests/{request_id}",
        headers=headers,
        json={"status": "in_progress"},
    )

    assert updated.status_code == 200
    assert updated.json["status"] == "in_progress"

    # Delete the maintenance request.
    deleted = client.delete(
        f"/api/maintenance-requests/{request_id}",
        headers=headers,
    )

    assert deleted.status_code == 204

    # Equipment can now be deleted.
    equipment_deleted = client.delete(
        f"/api/equipment/{equipment_id}",
        headers=admin_headers,
    )

    assert equipment_deleted.status_code == 204


def test_validation_and_conflicts(client):
    headers = login_headers(client)

    # Invalid email should be rejected.
    invalid = client.post(
        "/api/maintenance-staff",
        headers=headers,
        json={
            "name": "Test Staff",
            "email": "not-an-email",
        },
    )

    assert invalid.status_code == 400

    # Create a staff member with a valid email.
    created = client.post(
        "/api/maintenance-staff",
        headers=headers,
        json={
            "name": "Test Staff",
            "email": "duplicate@example.com",
        },
    )

    assert created.status_code == 201

    # Duplicate email should produce a conflict.
    duplicate = client.post(
        "/api/maintenance-staff",
        headers=headers,
        json={
            "name": "Another Staff",
            "email": "duplicate@example.com",
        },
    )

    assert duplicate.status_code == 409


def test_json_body_is_required(client):
    headers = login_headers(client)

    response = client.post(
        "/api/maintenance-staff",
        headers=headers,
    )

    assert response.status_code == 400


def test_successful_login(client):
    create_user(client)

    response = client.post(
        "/api/auth/login",
        json={
            "email": "technician-api-test@example.com",
            "password": "TestPass123",
        },
    )

    assert response.status_code == 200
    assert "access_token" in response.json
    assert response.json["token_type"] == "Bearer"


def test_login_rejects_wrong_password(client):
    create_user(client)

    response = client.post(
        "/api/auth/login",
        json={
            "email": "technician-api-test@example.com",
            "password": "WrongPassword123",
        },
    )

    assert response.status_code == 401


def test_inactive_user_cannot_login(client):
    create_user(client, is_active=False)

    response = client.post(
        "/api/auth/login",
        json={
            "email": "technician-api-test@example.com",
            "password": "TestPass123",
        },
    )

    assert response.status_code == 401


def test_login_requires_email_and_password(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "technician@example.com"},
    )

    assert response.status_code == 400


def test_user_maintenance_staff_relationship(client):
    with client.application.app_context():
        staff = MaintenanceStaff(
            name="Relationship Technician",
            email="relationship@example.com",
        )

        user = User(
            name="Relationship User",
            email="relationship-user@example.com",
            role="technician",
            must_change_password=False,
        )

        user.set_password("TestPass123")
        user.maintenance_staff = staff

        db.session.add(user)
        db.session.commit()

        assert user.maintenance_staff.id == staff.id
        assert staff.user.id == user.id


def test_registration_creates_technician_account(client):
    response = client.post(
        "/api/auth/register",
        json={
            "name": "New Technician",
            "email": "new@example.com",
            "password": "TestPass123",
        },
    )

    assert response.status_code == 201
    assert response.json["user"]["role"] == "technician"
    assert "password_hash" not in response.json["user"]


def test_registration_rejects_admin_role(client):
    response = client.post(
        "/api/auth/register",
        json={
            "name": "New Admin",
            "email": "newadmin@example.com",
            "password": "TestPass123",
            "role": "admin",
        },
    )

    assert response.status_code == 400


def test_registration_rejects_duplicate_email(client):
    payload = {
        "name": "New Technician",
        "email": "duplicate-user@example.com",
        "password": "TestPass123",
    }

    first = client.post("/api/auth/register", json=payload)
    second = client.post("/api/auth/register", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409
