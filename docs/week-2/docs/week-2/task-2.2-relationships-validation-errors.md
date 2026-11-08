Task 2.2 — Relationships, Validation and Error Handling

Project: ClinicFix API

1. Database Relationships

The API uses SQLAlchemy models and foreign-key constraints to maintain relationships between entities.

Implemented relationships include:

- User and MaintenanceStaff: one-to-one relationship.
- Equipment and MaintenanceRequest: equipment is referenced by maintenance requests.
- MaintenanceStaff and MaintenanceRequest: maintenance requests can be assigned to maintenance staff.

2. Input Validation

The API validates incoming request data before processing it. Validation covers required fields, data types, and invalid input values.

Validation logic is maintained in "clinicfix/validation.py".

3. Consistent Error Handling

The API returns structured JSON error responses for invalid requests and common application errors. Error responses use appropriate HTTP status codes rather than exposing internal implementation details.

4. Duplicate Records

Duplicate values for fields such as user email are handled appropriately. Duplicate registration returns HTTP 409 Conflict.

5. Parent-Child Deletion Protection

Equipment records with existing maintenance requests cannot be deleted. The API returns HTTP 409 Conflict to prevent the deletion from breaking related records.

6. Invalid and Missing Resources

Requests involving missing resources are handled with HTTP 404 Not Found responses.

7. Testing

Automated tests cover:

- User–MaintenanceStaff relationship handling.
- Duplicate email registration.
- Invalid input and validation errors.
- Equipment deletion restrictions.
- Resource and authentication errors.

Implementation files: "clinicfix/models.py", "clinicfix/validation.py", "clinicfix/routes.py", "clinicfix/app.py", and "tests/test_api.py".
