"""
Authentication Service
======================
Handles user registration, credential verification, JWT token generation,
password strength validation, and secure password reset workflows.
"""

import re
import secrets
from datetime import datetime, timedelta, timezone
from flask import current_app
from flask_jwt_extended import create_access_token, create_refresh_token
from models import db
from models.user import User, PasswordReset, UserPermission


class AuthService:
    """Service handling all authentication and password security operations."""

    @staticmethod
    def validate_password_strength(password: str) -> tuple[bool, str]:
        """
        Validates password complexity:
        - Must be longer than 8 characters (> 8, so at least 9 chars).
        - Must contain at least one uppercase letter.
        - Must contain at least one lowercase letter.
        - Must contain at least one special character.
        """
        if not password or len(password) <= 8:
            return False, "Password must be longer than 8 characters"
        if not re.search(r"[A-Z]", password):
            return False, "Password must contain at least one uppercase letter"
        if not re.search(r"[a-z]", password):
            return False, "Password must contain at least one lowercase letter"
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>[\]\\/'`~_+=;-]", password):
            return False, "Password must contain at least one special character"
        return True, ""

    @staticmethod
    def normalize_email(email: str) -> str:
        """Strips whitespace and converts email to lowercase."""
        return email.strip().lower() if email else ""

    @classmethod
    def register_customer(cls, data: dict) -> tuple[User | None, str | None]:
        """
        Registers a new customer account with full validations.
        """
        first_name = (data.get("first_name") or "").strip()
        last_name = (data.get("last_name") or "").strip()
        email = cls.normalize_email(data.get("email", ""))
        password = data.get("password", "")
        confirm_password = data.get("confirm_password", "")
        phone = (data.get("phone") or "").strip() or None

        # Required fields check
        if not first_name or not last_name or not email or not password:
            return None, "First name, last name, email, and password are required"

        # Email format check
        if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
            return None, "Invalid email address format"

        # Password confirmation check
        if password != confirm_password:
            return None, "Passwords do not match"

        # Password strength validation
        is_strong, err_msg = cls.validate_password_strength(password)
        if not is_strong:
            return None, err_msg

        # Duplicate email check
        if User.query.filter_by(email=email).first():
            return None, "An account with this email address already exists"

        # Create user
        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            role="customer",
            is_active=True,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        # Seed default module permissions for customer
        for module in ["products", "plans", "quotations", "subscriptions"]:
            perm = UserPermission(
                user_id=user.id,
                module_name=module,
                can_read=True,
                can_write=(module in ["quotations"]),
                can_delete=False,
            )
            db.session.add(perm)

        db.session.commit()
        return user, None

    @classmethod
    def authenticate_user(cls, email: str, password: str) -> tuple[dict | None, str | None]:
        """
        Authenticates user credentials and issues access and refresh tokens.
        """
        normalized_email = cls.normalize_email(email)
        if not normalized_email or not password:
            return None, "Email and password are required"

        user = User.query.filter_by(email=normalized_email).first()
        if not user or not user.check_password(password):
            return None, "Invalid email or password"

        if not user.is_active:
            return None, "Your account has been deactivated. Please contact support."

        # Generate tokens with claims
        additional_claims = {
            "role": user.role,
            "email": user.email,
            "full_name": user.full_name,
        }
        identity = str(user.id)

        access_token = create_access_token(identity=identity, additional_claims=additional_claims)
        refresh_token = create_refresh_token(identity=identity, additional_claims=additional_claims)

        return {
            "user": user.to_dict(include_permissions=True),
            "access_token": access_token,
            "refresh_token": refresh_token,
        }, None

    @classmethod
    def request_password_reset(cls, email: str) -> tuple[dict, str | None]:
        """
        Generates a secure, time-limited, single-use reset token.
        Never exposes whether an email exists in the database.
        Provides a safe development testing mechanism without weakening production security.
        """
        normalized_email = cls.normalize_email(email)
        generic_msg = "If your email is registered, you will receive password reset instructions."

        if not normalized_email:
            return {"message": generic_msg}, None

        user = User.query.filter_by(email=normalized_email).first()
        dev_token = None

        if user and user.is_active:
            # Generate cryptographically secure token
            token = secrets.token_urlsafe(32)
            expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

            reset_record = PasswordReset(
                user_id=user.id,
                token=token,
                expires_at=expires_at,
                is_used=False,
            )
            db.session.add(reset_record)
            db.session.commit()

            # Safe dev testing mechanism: expose token ONLY in DEBUG/development mode
            is_debug = current_app.config.get("DEBUG", False)
            if is_debug:
                dev_token = token

        result = {"message": generic_msg}
        if dev_token:
            result["dev_reset_token"] = dev_token

        return result, None

    @classmethod
    def reset_password(cls, token: str, new_password: str, confirm_password: str) -> tuple[bool, str | None]:
        """
        Validates token and updates user password.
        """
        if not token:
            return False, "Reset token is required"

        if new_password != confirm_password:
            return False, "Passwords do not match"

        is_strong, err_msg = cls.validate_password_strength(new_password)
        if not is_strong:
            return False, err_msg

        reset_record = PasswordReset.query.filter_by(token=token).first()
        if not reset_record:
            return False, "Invalid or expired reset token"

        if reset_record.is_used:
            return False, "This reset token has already been used"

        if reset_record.is_expired:
            return False, "This reset token has expired. Please request a new one"

        user = db.session.get(User, reset_record.user_id)
        if not user or not user.is_active:
            return False, "Associated user account is invalid or inactive"

        user.set_password(new_password)
        reset_record.is_used = True
        db.session.commit()

        return True, None

