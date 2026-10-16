"""Small, explicit JSON validation helpers for the API."""

import re


RULES = {
    "equipment": {
        "name": ("text", 120),
        "category": ("text", 80),
        "serial_number": ("optional_text", 100),
        "location": ("text", 120),
        "status": ("choice", {"active", "maintenance", "retired"}),
    },
    "staff": {
        "name": ("text", 120),
        "email": ("email", 254),
        "phone": ("optional_text", 40),
        "specialty": ("optional_text", 100),
        "is_active": ("boolean",),
    },
    "request": {
        "equipment_id": ("positive_id",),
        "assigned_staff_id": ("optional_id",),
        "description": ("text", 1000),
        "priority": ("choice", {"low", "medium", "high", "urgent"}),
        "status": ("choice", {"open", "in_progress", "completed"}),
    },
}

REQUIRED = {
    "equipment": {"name", "category", "location"},
    "staff": {"name", "email"},
    "request": {"equipment_id", "description"},
}


def validate_payload(payload, resource, *, partial=False):
    """Return a sanitized payload and a list of human-readable validation errors."""
    if not isinstance(payload, dict):
        return {}, ["Request body must be a JSON object."]

    rules = RULES[resource]
    errors = []
    unknown_fields = sorted(set(payload) - set(rules))
    if unknown_fields:
        errors.append(f"Unknown field(s): {', '.join(unknown_fields)}.")

    if not partial:
        for field in sorted(REQUIRED[resource] - set(payload)):
            errors.append(f"'{field}' is required.")
    elif not payload:
        errors.append("Provide at least one field to update.")

    clean = {}
    for field, value in payload.items():
        if field not in rules:
            continue

        rule = rules[field]
        kind = rule[0]
        if kind == "optional_text" and value is None:
            clean[field] = None
        elif kind == "optional_id" and value is None:
            clean[field] = None
        elif kind in {"text", "optional_text"}:
            if not isinstance(value, str):
                errors.append(f"'{field}' must be text.")
                continue
            value = value.strip()
            if kind == "text" and not value:
                errors.append(f"'{field}' cannot be blank.")
            elif len(value) > rule[1]:
                errors.append(f"'{field}' must be {rule[1]} characters or fewer.")
            else:
                clean[field] = value or None
        elif kind == "email":
            if not isinstance(value, str):
                errors.append("'email' must be text.")
                continue
            value = value.strip()
            if len(value) > rule[1] or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
                errors.append("'email' must be a valid email address.")
            else:
                clean[field] = value.lower()
        elif kind == "choice":
            if not isinstance(value, str) or value not in rule[1]:
                choices = ", ".join(sorted(rule[1]))
                errors.append(f"'{field}' must be one of: {choices}.")
            else:
                clean[field] = value
        elif kind == "boolean":
            if not isinstance(value, bool):
                errors.append("'is_active' must be true or false.")
            else:
                clean[field] = value
        elif kind in {"positive_id", "optional_id"}:
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                errors.append(f"'{field}' must be a positive integer.")
            else:
                clean[field] = value

    return clean, errors
