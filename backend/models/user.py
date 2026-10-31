"""
User and Authentication Models
==============================
Defines User, PasswordReset, and UserPermission entities.
"""

from datetime import datetime, timezone
from sqlalchemy.ext.hybrid import hybrid_property
from werkzeug.security import generate_password_hash, check_password_hash
from models import db


class User(db.Model):
    """User account entity supporting Admin, Staff, and Customer roles."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(60), nullable=False)
    last_name = db.Column(db.String(60), nullable=False)
    phone = db.Column(db.String(30), nullable=True)
    role = db.Column(db.String(20), nullable=False, default="customer")  # admin, staff, customer
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    permissions = db.relationship("UserPermission", backref="user", cascade="all, delete-orphan", lazy="dynamic")
    password_resets = db.relationship("PasswordReset", backref="user", cascade="all, delete-orphan", lazy="dynamic")

    def set_password(self, password: str):
        """Hashes and sets the password using Werkzeug pbkdf2:sha256."""
        self.password_hash = generate_password_hash(password, method="pbkdf2:sha256")

    def check_password(self, password: str) -> bool:
        """Verifies the password against the stored hash."""
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @hybrid_property
    def name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @name.expression
    def name(cls):
        return db.func.trim(cls.first_name + " " + cls.last_name)

    def to_dict(self, include_permissions: bool = False) -> dict:
        """Serializes user model to dictionary."""
        data = {
            "id": self.id,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "phone": self.phone,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_permissions:
            data["permissions"] = [p.to_dict() for p in self.permissions.all()]
        return data


class PasswordReset(db.Model):
    """Tracks time-limited, single-use password reset tokens."""
    __tablename__ = "password_resets"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token = db.Column(db.String(128), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_used = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at.replace(tzinfo=timezone.utc) if self.expires_at.tzinfo is None else datetime.now(timezone.utc) > self.expires_at


class UserPermission(db.Model):
    """Granular module-level permissions for users."""
    __tablename__ = "user_permissions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    module_name = db.Column(db.String(50), nullable=False)  # users, products, plans, quotations, subscriptions
    can_read = db.Column(db.Boolean, default=True, nullable=False)
    can_write = db.Column(db.Boolean, default=False, nullable=False)
    can_delete = db.Column(db.Boolean, default=False, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "module_name", name="uq_user_module_permission"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "module_name": self.module_name,
            "can_read": self.can_read,
            "can_write": self.can_write,
            "can_delete": self.can_delete,
        }

