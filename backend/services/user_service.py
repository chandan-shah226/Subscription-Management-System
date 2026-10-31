"""
User Management Service
=======================
Handles user querying, staff account creation, permission management,
account status updates, and prevention of unauthorized role escalation.
"""

import re
from models import db
from models.user import User, UserPermission
from services.auth_service import AuthService


class UserService:
    """Service handling administrative and user profile management."""

    @staticmethod
    def list_users(role_filter: str | None = None, is_active: bool | None = None, search: str | None = None):
        """Retrieves users with optional filtering."""
        query = User.query

        if role_filter:
            query = query.filter_by(role=role_filter)
        if is_active is not None:
            query = query.filter_by(is_active=is_active)
        if search:
            search_term = f"%{search.strip().lower()}%"
            query = query.filter(
                (User.email.ilike(search_term)) |
                (User.first_name.ilike(search_term)) |
                (User.last_name.ilike(search_term))
            )

        return [user.to_dict(include_permissions=True) for user in query.order_by(User.created_at.desc()).all()]

    @staticmethod
    def get_user_by_id(user_id: int):
        """Retrieves a single user with permissions."""
        user = db.session.get(User, user_id)
        return user.to_dict(include_permissions=True) if user else None

    @classmethod
    def create_staff_user(cls, data: dict, creator_role: str) -> tuple[dict | None, str | None]:
        """
        Creates a staff account.
        Rules:
        - Only Admin can create staff accounts.
        - Staff must NOT create admin accounts.
        """
        if creator_role != "admin":
            return None, "Only administrators can create staff accounts"

        target_role = data.get("role", "staff")
        if target_role not in ["staff", "customer"]:
            return None, "Cannot create users with role other than staff or customer"

        first_name = (data.get("first_name") or "").strip()
        last_name = (data.get("last_name") or "").strip()
        email = AuthService.normalize_email(data.get("email", ""))
        password = data.get("password", "")
        phone = (data.get("phone") or "").strip() or None

        if not first_name or not last_name or not email or not password:
            return None, "First name, last name, email, and password are required"

        is_strong, err_msg = AuthService.validate_password_strength(password)
        if not is_strong:
            return None, err_msg

        if User.query.filter_by(email=email).first():
            return None, "An account with this email address already exists"

        user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            role=target_role,
            is_active=True,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        # Seed module permissions
        for module in ["products", "plans", "quotations", "subscriptions", "users"]:
            can_w = target_role == "staff" and module != "users"
            can_d = target_role == "staff" and module in ["quotations", "subscriptions"]
            perm = UserPermission(
                user_id=user.id,
                module_name=module,
                can_read=True,
                can_write=can_w,
                can_delete=can_d,
            )
            db.session.add(perm)

        db.session.commit()
        return user.to_dict(include_permissions=True), None

    @classmethod
    def update_user(cls, user_id: int, data: dict, modifier_role: str) -> tuple[dict | None, str | None]:
        """
        Updates user details.
        Enforces role escalation prevention.
        """
        user = db.session.get(User, user_id)
        if not user:
            return None, "User not found"

        # Update basic profile
        if "first_name" in data and data["first_name"].strip():
            user.first_name = data["first_name"].strip()
        if "last_name" in data and data["last_name"].strip():
            user.last_name = data["last_name"].strip()
        if "phone" in data:
            user.phone = data["phone"].strip() or None

        # Role modification rules
        if "role" in data:
            target_role = data["role"]
            if modifier_role != "admin":
                return None, "Only administrators can change user roles"
            if target_role not in ["admin", "staff", "customer"]:
                return None, "Invalid role specified"
            user.role = target_role

        # Active status modification rules
        if "is_active" in data:
            if modifier_role not in ["admin", "staff"]:
                return None, "Only administrators or staff can activate/deactivate accounts"
            user.is_active = bool(data["is_active"])

        # Update permissions if provided (Admin only)
        if "permissions" in data and modifier_role == "admin":
            for p_data in data["permissions"]:
                mod = p_data.get("module_name")
                if not mod:
                    continue
                perm = UserPermission.query.filter_by(user_id=user.id, module_name=mod).first()
                if not perm:
                    perm = UserPermission(user_id=user.id, module_name=mod)
                    db.session.add(perm)
                perm.can_read = bool(p_data.get("can_read", True))
                perm.can_write = bool(p_data.get("can_write", False))
                perm.can_delete = bool(p_data.get("can_delete", False))

        db.session.commit()
        return user.to_dict(include_permissions=True), None

    @classmethod
    def toggle_user_active(cls, user_id: int, modifier_id: int, modifier_role: str) -> tuple[dict | None, str | None]:
        """Toggles account active state. Prevents an admin from deactivating themselves."""
        if modifier_role not in ["admin", "staff"]:
            return None, "Permission denied"

        if user_id == modifier_id:
            return None, "You cannot deactivate your own account"

        user = db.session.get(User, user_id)
        if not user:
            return None, "User not found"

        if user.role == "admin" and modifier_role != "admin":
            return None, "Cannot modify an administrator account"

        user.is_active = not user.is_active
        db.session.commit()
        return user.to_dict(), None

