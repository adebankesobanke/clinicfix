
from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    get_jwt_identity,
    jwt_required,
)
from sqlalchemy.exc import IntegrityError

from .models import Equipment, MaintenanceRequest, MaintenanceStaff, User, db
from .validation import validate_payload

api = Blueprint("api", __name__)

RESOURCES = {
    "equipment": (Equipment, "equipment"),
    "maintenance-staff": (MaintenanceStaff, "staff"),
    "maintenance-requests": (MaintenanceRequest, "request"),
}

def error(message, status):
    return jsonify({"error": message}), status


def validation_error(messages):
    return error(" ".join(messages), 400)


def read_payload(resource, *, partial=False):
    if not request.is_json:
        return None, ["Content-Type must be application/json."]

    payload = request.get_json(silent=True)
    return validate_payload(payload, resource, partial=partial)


def commit_record():
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return error(
            "A unique value is already in use or a related record prevents this change.",
            409,
        )
    return None


def check_references(values):
    if (
        "equipment_id" in values
        and db.session.get(Equipment, values["equipment_id"]) is None
    ):
        return error("Equipment was not found.", 404)

    staff_id = values.get("assigned_staff_id")
    if staff_id is not None and db.session.get(MaintenanceStaff, staff_id) is None:
        return error("Maintenance staff member was not found.", 404)

    return None


def can_manage_request(user, maintenance_request):
    """Check whether a user may update or delete a maintenance request."""

    if user.role == "admin":
        return True

    if user.role != "technician":
        return False

    if user.maintenance_staff_id is None:
        return False

    return (
        maintenance_request.assigned_staff_id
        == user.maintenance_staff_id
    )


@api.get("/healthz")
def health():
    return jsonify({"status": "ok", "service": "ClinicFix API"})


@api.post("/auth/register")
def register():
    values, errors = read_payload("user")

    if errors:
        return validation_error(errors)

    email = values["email"]

    existing_user = User.query.filter_by(email=email).first()

    if existing_user is not None:
        return error("An account with this email already exists.", 409)

    user = User(
        name=values["name"],
        email=email,
        role="technician",
        is_active=True,
        must_change_password=True,
    )
    user.set_password(values["password"])

    db.session.add(user)

    conflict = commit_record()

    if conflict:
        return conflict

    return jsonify({
        "message": "Registration successful.",
        "user": user.to_dict(),
    }), 201


@api.post("/auth/login")
def login():
    if not request.is_json:
        return error("Email and password are required.", 400)

    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return error("Email and password are required.", 400)

    email = payload.get("email")
    password = payload.get("password")

    if (
        not isinstance(email, str)
        or not email.strip()
        or not isinstance(password, str)
        or not password.strip()
    ):
        return error("Email and password are required.", 400)

    user = User.query.filter_by(email=email.strip().lower()).first()

    if user is None or not user.is_active or not user.check_password(password):
        return error("Invalid email or password.", 401)

    access_token = create_access_token(identity=str(user.id))

    return jsonify({
        "access_token": access_token,
        "token_type": "Bearer",
        "must_change_password": user.must_change_password,
    }), 200


@api.post("/auth/change-password")
@jwt_required()
def change_password():
    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id))

    if user is None:
        return error("User account was not found.", 401)

    if not user.is_active:
        return error("User account is inactive.", 403)

    if not request.is_json:
        return error("Current and new passwords are required.", 400)

    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return error("Current and new passwords are required.", 400)

    current_password = payload.get("current_password")
    new_password = payload.get("new_password")

    if (
        not isinstance(current_password, str)
        or not current_password
        or not isinstance(new_password, str)
        or not new_password.strip()
    ):
        return error("Current and new passwords are required.", 400)

    if not user.check_password(current_password):
        return error("Current password is incorrect.", 401)

    if len(new_password) < 8:
        return error("New password must contain at least 8 characters.", 400)

    if len(new_password.encode("utf-8")) > 72:
        return error("New password must not exceed 72 bytes.", 400)

    if new_password != new_password.strip():
        return error("New password cannot begin or end with spaces.", 400)

    if current_password == new_password:
        return error("New password must differ from current password.", 400)

    user.set_password(new_password)
    user.must_change_password = False

    conflict = commit_record()

    if conflict:
        return conflict

    return jsonify({"message": "Password changed successfully."}), 200


@api.route(
    "/<resource_path>",
    defaults={"record_id": None},
    methods=["GET", "POST"],
)
@api.route(
    "/<resource_path>/<int:record_id>",
    methods=["GET", "PATCH", "DELETE"],
)
@jwt_required()
def records(resource_path, record_id):

    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id))

    if user is None:
        return error("User account was not found.", 401)

    if not user.is_active:
        return error("User account is inactive.", 403)

    if user.must_change_password:
        return error(
            "You must change your password before accessing resources.",
            403,
        )

    resource = RESOURCES.get(resource_path)

    if resource is None:
        return error("Route was not found.", 404)

    resource_class, resource_name = resource

    # Only administrators can manage maintenance staff.
    if (
        resource_name == "staff"
        and request.method in {"POST", "PATCH", "DELETE"}
        and user.role != "admin"
    ):
        return error(
            "Only administrators can manage maintenance staff.",
            403,
        )


    # GET: Retrieve records.
    if request.method == "GET":
        if record_id is None:
            return jsonify(
                [
                    record.to_dict()
                    for record in resource_class.query.order_by(resource_class.id)
                ]
            )

        record = db.session.get(resource_class, record_id)

        if record is None:
            return error("Record was not found.", 404)

        return jsonify(record.to_dict())

    # POST: Create a new record.
    if request.method == "POST":
        if resource_name == "equipment" and user.role != "admin":
            return error("Only administrators can create equipment.", 403)

        values, errors = read_payload(resource_name)

        if errors:
            return validation_error(errors)

        if resource_name == "request":
            reference_error = check_references(values)

            if reference_error:
                return reference_error

        record = resource_class(**values)
        db.session.add(record)

        conflict = commit_record()

        if conflict:
            return conflict

        return jsonify(record.to_dict()), 201

    # Retrieve the existing record for PATCH or DELETE.
    record = db.session.get(resource_class, record_id)

    if record is None:
        return error("Record was not found.", 404)

    # Check ownership before updating or deleting a maintenance request.
    if (
        resource_name == "request"
        and not can_manage_request(user, record)
    ):
        return error(
            "You are not authorised to manage this maintenance request.",
            403,
        )

    # PATCH: Update an existing record.
    if request.method == "PATCH":
        if resource_name == "equipment" and user.role != "admin":
            return error("Only administrators can update equipment.", 403)

        values, errors = read_payload(resource_name, partial=True)

        if errors:
            return validation_error(errors)




        if resource_name == "request":
            # Only administrators can reassign maintenance requests.
            if (
                "assigned_staff_id" in values
                and user.role != "admin"
            ):
                return error(
                    "Only administrators can reassign maintenance requests.",
                    403,
                )

            reference_error = check_references(values)

            if reference_error:
                return reference_error



        for field, value in values.items():
            setattr(record, field, value)

        conflict = commit_record()

        if conflict:
            return conflict

        return jsonify(record.to_dict())

    # DELETE: Remove an existing record.
    if request.method == "DELETE":
        if resource_name == "equipment" and user.role != "admin":
            return error("Only administrators can delete equipment.", 403)

        if (
            resource_name == "equipment"
            and MaintenanceRequest.query.filter_by(
                equipment_id=record.id
            ).first()
        ):
            return error(
                "Equipment with maintenance requests cannot be deleted. "
                "Delete or reassign its requests first.",
                409,
            )

        if resource_name == "staff":
            MaintenanceRequest.query.filter_by(
                assigned_staff_id=record.id
            ).update({"assigned_staff_id": None})

        db.session.delete(record)

        conflict = commit_record()

        if conflict:
            return conflict

        return "", 204
