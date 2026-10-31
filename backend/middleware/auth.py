"""
Authentication, Authorization & Response Middleware
==================================================
Provides role-based access control (RBAC), module-level permission guards,
IDOR prevention, and standardized JSON response helpers.
"""

from functools import wraps
from flask import jsonify, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, get_jwt
from models import db
from models.user import User, UserPermission


def api_response(data=None, message="", status_code=200):
    """Generates a standardized JSON success response envelope."""
    payload = {
        "success": True,
        "message": message,
        "data": data if data is not None else {}
    }
    return jsonify(payload), status_code


def api_error(error="", status_code=400, details=None):
    """Generates a standardized JSON error response envelope."""
    payload = {
        "success": False,
        "error": error,
        "details": details if details is not None else {}
    }
    return jsonify(payload), status_code


def get_current_user():
    """Retrieves the authenticated User instance for the current JWT identity."""
    verify_jwt_in_request()
    identity = get_jwt_identity()
    try:
        user_id = int(identity) if identity is not None else None
    except (ValueError, TypeError):
        user_id = None
    return db.session.get(User, user_id) if user_id else None


def roles_required(*allowed_roles):
    """
    Decorator enforcing that the authenticated user possesses one of the allowed roles.
    Also verifies that the account is active.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            role = claims.get("role")
            identity = get_jwt_identity()
            try:
                user_id = int(identity) if identity is not None else None
            except (ValueError, TypeError):
                user_id = None

            user = db.session.get(User, user_id) if user_id else None
            if not user or not user.is_active:
                return api_error("User account is inactive or no longer exists", 403)

            if role not in allowed_roles:
                return api_error(
                    f"Access forbidden: requires one of the following roles: {', '.join(allowed_roles)}",
                    403
                )
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def permission_required(module_name: str, action: str = "read"):
    """
    Decorator enforcing module-level permissions (users, products, plans, quotations, subscriptions).
    Admins bypass permission checks. Staff and Customers are validated against UserPermission.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user = get_current_user()
            if not user or not user.is_active:
                return api_error("User account is inactive", 403)

            if user.role == "admin":
                return fn(*args, **kwargs)

            # Check module permission
            perm = UserPermission.query.filter_by(user_id=user.id, module_name=module_name).first()
            if not perm:
                # Default baseline permissions if not explicitly granted
                if user.role == "staff" and action in ["read", "write"]:
                    return fn(*args, **kwargs)
                return api_error(f"Permission denied for module '{module_name}'", 403)

            has_perm = False
            if action == "read" and perm.can_read:
                has_perm = True
            elif action == "write" and perm.can_write:
                has_perm = True
            elif action == "delete" and perm.can_delete:
                has_perm = True

            if not has_perm:
                return api_error(f"Insufficient permissions to {action} in module '{module_name}'", 403)

            return fn(*args, **kwargs)
        return wrapper
    return decorator


def prevent_customer_idor(target_customer_id: int, current_user: User) -> bool:
    """
    Returns True if current_user is allowed to access target_customer_id data.
    Staff and Admin can access any customer's records.
    Customer can ONLY access their own records.
    """
    if current_user.role in ["admin", "staff"]:
        return True
    return current_user.id == target_customer_id

