from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, jwt_required
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
    if "equipment_id" in values and db.session.get(Equipment, values["equipment_id"]) is None:
        return error("Equipment was not found.", 404)
    staff_id = values.get("assigned_staff_id")
    if staff_id is not None and db.session.get(MaintenanceStaff, staff_id) is None:
        return error("Maintenance staff member was not found.", 404)
    return None


@api.get("/healthz")
def health():
    return jsonify({"status": "ok", "service": "ClinicFix API"})


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
    return jsonify({"access_token": access_token, "token_type": "Bearer"}), 200


@api.route("/<resource_path>", defaults={"record_id": None}, methods=["GET", "POST"])
@api.route("/<resource_path>/<int:record_id>", methods=["GET", "PATCH", "DELETE"])
@jwt_required()
def records(resource_path, record_id):
    resource = RESOURCES.get(resource_path)
    if resource is None:
        return error("Route was not found.", 404)
    resource_class, resource_name = resource

    if request.method == "GET":
        if record_id is None:
            return jsonify([record.to_dict() for record in resource_class.query.order_by(resource_class.id)])
        record = db.session.get(resource_class, record_id)
        if record is None:
            return error("Record was not found.", 404)
        return jsonify(record.to_dict())

    if request.method == "POST":
        values, errors = read_payload(resource_name)
        if errors:
            return jsonify({"errors": errors}), 400
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

    record = db.session.get(resource_class, record_id)
    if record is None:
        return error("Record was not found.", 404)

    if request.method == "PATCH":
        values, errors = read_payload(resource_name, partial=True)
        if errors:
            return jsonify({"errors": errors}), 400
        if resource_name == "request":
            reference_error = check_references(values)
            if reference_error:
                return reference_error
        for field, value in values.items():
            setattr(record, field, value)
        conflict = commit_record()
        if conflict:
            return conflict
        return jsonify(record.to_dict())

    if resource_name == "equipment" and MaintenanceRequest.query.filter_by(
        equipment_id=record.id
    ).first():
        return error(
            "Equipment with maintenance requests cannot be deleted. Delete or reassign its requests first.",
            409,
        )
    if resource_name == "staff":
        MaintenanceRequest.query.filter_by(assigned_staff_id=record.id).update(
            {"assigned_staff_id": None}
        )
    db.session.delete(record)
    conflict = commit_record()
    if conflict:
        return conflict
    return "", 204
