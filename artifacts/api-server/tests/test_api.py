
from datetime import timedelta

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


def test_invalid_token_returns_consistent_json_error(client):
    response = client.get(
        "/api/equipment",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401
    assert response.get_json() == {
        "error": "Authentication token is invalid."
    }


def test_expired_token_returns_consistent_json_error(client):
    from flask_jwt_extended import create_access_token

    with client.application.app_context():
        token = create_access_token(
            identity="1",
            expires_delta=timedelta(seconds=-1),
        )

    response = client.get(
        "/api/equipment",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.get_json() == {
        "error": "Authentication token has expired."
    }


def test_resource_access_requires_authentication(client):
    response = client.get("/api/equipment")

    assert response.status_code == 401
    assert response.get_json() == {
        "error": "Authentication token is required."
    }


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
    # Staff creation and management are tested using an administrator.
    headers = login_headers(client, "admin")

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
    technician_headers = login_headers(client, "technician")
    admin_headers = login_headers(client, "admin")

    # Administrator creates equipment.
    equipment_response = create_equipment(client, admin_headers)
    assert equipment_response.status_code == 201

    equipment_id = equipment_response.json["id"]

    # Administrator creates a maintenance staff record.
    staff_response = client.post(
        "/api/maintenance-staff",
        headers=admin_headers,
        json={
            "name": "Jane Technician",
            "email": "jane@example.com",
        },
    )

    assert staff_response.status_code == 201
    staff_id = staff_response.json["id"]

    # Link the technician's user account to this staff account.
    with client.application.app_context():
        technician = User.query.filter_by(
            email="technician-api-test@example.com"
        ).first()

        technician.maintenance_staff_id = staff_id
        db.session.commit()

    # Technician creates a maintenance request assigned to themselves.
    created = client.post(
        "/api/maintenance-requests",
        headers=technician_headers,
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
        headers=technician_headers,
    )

    assert retrieved.status_code == 200
    assert retrieved.json["equipment_id"] == equipment_id

    # The assigned technician can update their own request.
    updated = client.patch(
        f"/api/maintenance-requests/{request_id}",
        headers=technician_headers,
        json={"status": "in_progress"},
    )

    assert updated.status_code == 200
    assert updated.json["status"] == "in_progress"

    # The assigned technician can delete their own request.
    deleted = client.delete(
        f"/api/maintenance-requests/{request_id}",
        headers=technician_headers,
    )

    assert deleted.status_code == 204

    # Equipment can now be deleted.
    equipment_deleted = client.delete(
        f"/api/equipment/{equipment_id}",
        headers=admin_headers,
    )

    assert equipment_deleted.status_code == 204


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


def test_user_must_change_password_before_accessing_resources(client):
    # Log in a test user.
    headers = login_headers(client, "technician")

    # Mark the user as requiring a password change.
    with client.application.app_context():
        user = User.query.filter_by(
            email="technician-api-test@example.com"
        ).first()

        user.must_change_password = True
        db.session.commit()

    # The user cannot access equipment before changing the password.
    blocked = client.get(
        "/api/equipment",
        headers=headers,
    )

    assert blocked.status_code == 403
    assert blocked.json["error"] == (
        "You must change your password before accessing resources."
    )

    # The user can change their password.
    changed = client.post(
        "/api/auth/change-password",
        headers=headers,
        json={
            "current_password": "TestPass123",
            "new_password": "NewSecurePass456",
        },
    )

    assert changed.status_code == 200

    # The user can now access equipment.
    allowed = client.get(
        "/api/equipment",
        headers=headers,
    )

    assert allowed.status_code == 200

    # Verify the password-change flag and new password.
    with client.application.app_context():
        user = User.query.filter_by(
            email="technician-api-test@example.com"
        ).first()

        assert user.must_change_password is False
        assert user.check_password("NewSecurePass456")


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


def test_technician_cannot_manage_another_technicians_request(client):
    # Log in two different technicians and an administrator.
    technician_a_headers = login_headers(client, "technician_a")
    technician_b_headers = login_headers(client, "technician_b")
    admin_headers = login_headers(client, "admin")

    # Administrator creates equipment.
    equipment_response = create_equipment(client, admin_headers)
    assert equipment_response.status_code == 201

    equipment_id = equipment_response.json["id"]

    # Administrator creates a maintenance staff record for Technician B.
    staff_response = client.post(
        "/api/maintenance-staff",
        headers=admin_headers,
        json={
            "name": "Technician B",
            "email": "technician-b@example.com",
        },
    )

    assert staff_response.status_code == 201
    staff_id = staff_response.json["id"]

    # Link Technician B's user account to the staff record.
    with client.application.app_context():
        technician_b = User.query.filter_by(
            email="technician_b-api-test@example.com"
        ).first()

        technician_b.maintenance_staff_id = staff_id
        db.session.commit()

    # Technician B creates a request assigned to themselves.
    created = client.post(
        "/api/maintenance-requests",
        headers=technician_b_headers,
        json={
            "equipment_id": equipment_id,
            "assigned_staff_id": staff_id,
            "description": "Generator is not starting.",
            "priority": "high",
        },
    )

    assert created.status_code == 201
    request_id = created.json["id"]

    # Technician A must not update Technician B's request.
    update_response = client.patch(
        f"/api/maintenance-requests/{request_id}",
        headers=technician_a_headers,
        json={"status": "in_progress"},
    )

    assert update_response.status_code == 403

    # Technician A must not delete Technician B's request.
    delete_response = client.delete(
        f"/api/maintenance-requests/{request_id}",
        headers=technician_a_headers,
    )

    assert delete_response.status_code == 403

    # Administrator can still manage the request.
    admin_update = client.patch(
        f"/api/maintenance-requests/{request_id}",
        headers=admin_headers,
        json={"status": "in_progress"},
    )

    assert admin_update.status_code == 200


def test_validation_errors_use_consistent_json_format(client):
    response = client.post(
        "/api/auth/register",
        json={
            "name": "",
            "email": "invalid-email",
            "password": "123",
        },
    )

    assert response.status_code == 400
    assert "error" in response.get_json()
    assert "errors" not in response.get_json()
