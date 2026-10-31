"""
Authentication & Authorization Middleware
=========================================
Provides role-based access decorators and customer boundary isolation checks.
Supports JWT tokens as well as demo user switching headers.
"""

from functools import wraps
from flask import request, jsonify, g
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from models import db, User


def get_current_user():
    """Retrieves the currently authenticated user for the current request."""
    # Check for X-Demo-User header first (for testing and quick role switching)
    demo_email_or_role = request.headers.get("X-Demo-User")
    if demo_email_or_role:
        user = User.query.filter(
            (User.email == demo_email_or_role) | (User.role == demo_email_or_role)
        ).first()
        if user and user.is_active:
            g.current_user = user
            return user

    try:
        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
        if identity is not None:
            user_id = int(identity) if str(identity).isdigit() else None
            if user_id:
                user = db.session.get(User, user_id)
                if user and user.is_active:
                    g.current_user = user
                    return user
    except Exception:
        pass

    return None


def auth_required(f):
    """Requires a valid authenticated user."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({
                "success": False,
                "error": "Authentication required. Please provide a valid Bearer token."
            }), 401
        return f(*args, **kwargs)
    return decorated_function


def roles_required(*allowed_roles):
    """Requires current user to possess at least one of the specified roles."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({
                    "success": False,
                    "error": "Authentication required."
                }), 401

            if user.role not in allowed_roles:
                return jsonify({
                    "success": False,
                    "error": f"Forbidden: Action requires one of roles: {', '.join(allowed_roles)}. Your role is '{user.role}'."
                }), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def verify_customer_access(invoice, user):
    """
    Customer isolation guard:
    Customers can only access their own invoices.
    Admins and Staff have universal operational visibility.
    If unauthenticated (e.g. direct print link), permitted unless explicitly restricted.
    """
    if not user:
        return True
    if user.role == "customer" and invoice.customer_id != user.id:
        return False
    return True
