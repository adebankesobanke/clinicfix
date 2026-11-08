Task 2.1 — Authentication and Authorization

Project: ClinicFix API

1. User Registration and Login

The API supports user registration and login. Users authenticate using their registered email address and password. Successful login returns a JSON Web Token (JWT).

2. Password Security

User passwords are stored as password hashes rather than plain text. Password verification is performed during login.

3. Protected Routes

JWT authentication is required to access protected API resources. Unauthenticated requests are rejected with HTTP 401 Unauthorized.

4. Role-Based Access Control

The API supports two user roles:

- Administrator
- Technician

Administrative operations, including equipment creation, updating and deletion, are restricted to administrators. Users without the required permissions receive HTTP 403 Forbidden.

5. Ownership Checks

Maintenance-request access includes ownership restrictions so that technicians cannot manage another technician's requests.

6. Error Responses

The API uses appropriate HTTP status codes:

- 401 — Unauthenticated or invalid authentication.
- 403 — Authenticated user lacks the required permission.
- 404 — Requested resource not found.

7. Testing

Automated tests cover authentication, invalid and expired tokens, login failures, role restrictions, registration and maintenance-request ownership.

Implementation files: "clinicfix/models.py", "clinicfix/routes.py", "clinicfix/app.py", and "tests/test_api.py".
