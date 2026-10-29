from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Equipment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    serial_number = db.Column(db.String(100), unique=True, nullable=True)
    location = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="active")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "serial_number": self.serial_number,
            "location": self.location,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


class MaintenanceStaff(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), nullable=False, unique=True)
    phone = db.Column(db.String(40), nullable=True)
    specialty = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    user = db.relationship(
        "User",
        back_populates="maintenance_staff",
        uselist=False,
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "specialty": self.specialty,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
        }


class MaintenanceRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(
        db.Integer, db.ForeignKey("equipment.id", ondelete="RESTRICT"), nullable=False
    )
    assigned_staff_id = db.Column(
        db.Integer, db.ForeignKey("maintenance_staff.id", ondelete="SET NULL"), nullable=True
    )
    description = db.Column(db.String(1000), nullable=False)
    priority = db.Column(db.String(20), nullable=False, default="medium")
    status = db.Column(db.String(20), nullable=False, default="open")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "equipment_id": self.equipment_id,
            "assigned_staff_id": self.assigned_staff_id,
            "description": self.description,
            "priority": self.priority,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), nullable=False, unique=True)
    password_hash = db.Column(db.String(256), nullable=False)
    maintenance_staff_id = db.Column(
        db.Integer,
        db.ForeignKey("maintenance_staff.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )
    maintenance_staff = db.relationship(
        "MaintenanceStaff",
        back_populates="user",
        uselist=False,
    )
    role = db.Column(db.String(20), nullable=False, default="technician")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    must_change_password = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utc_now
    )

    def set_password(self, password: str) -> None:
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "must_change_password": self.must_change_password,
            "created_at": self.created_at.isoformat(),
        }
