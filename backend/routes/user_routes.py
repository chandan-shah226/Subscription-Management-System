"""
User Management API Endpoints
=============================
Routes for administrative user listing, staff creation, profile updates,
and active status toggling.
"""

from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt
from middleware.auth import api_response, api_error, get_current_user, roles_required, prevent_customer_idor
from services.user_service import UserService

user_bp = Blueprint("users", __name__, url_prefix="/api/users")


@user_bp.route("", methods=["GET"])
@jwt_required()
@roles_required("admin", "staff")
def list_users():
    """Lists users with optional role, is_active, and search query filters."""
    role_filter = request.args.get("role")
    is_active_arg = request.args.get("is_active")
    search = request.args.get("search")

    is_active = None
    if is_active_arg is not None:
        is_active = is_active_arg.lower() in ["true", "1"]

    users = UserService.list_users(role_filter=role_filter, is_active=is_active, search=search)
    return api_response(data=users, status_code=200)


@user_bp.route("/<int:user_id>", methods=["GET"])
@jwt_required()
def get_user(user_id):
    """Retrieves a single user. Customers can only view their own user account."""
    current_user = get_current_user()
    if not current_user:
        return api_error("User not found", 404)

    if not prevent_customer_idor(user_id, current_user):
        return api_error("Access forbidden: you can only access your own profile", 403)

    user = UserService.get_user_by_id(user_id)
    if not user:
        return api_error("User not found", 404)
    return api_response(data=user, status_code=200)


@user_bp.route("", methods=["POST"])
@jwt_required()
@roles_required("admin")
def create_staff():
    """Admin-only endpoint to create staff and customer accounts."""
    claims = get_jwt()
    creator_role = claims.get("role")
    data = request.get_json() or {}

    user, error = UserService.create_staff_user(data, creator_role)
    if error:
        return api_error(error, 400)
    return api_response(data=user, message="User account created successfully", status_code=201)


@user_bp.route("/<int:user_id>", methods=["PUT"])
@jwt_required()
def update_user(user_id):
    """Updates user information with role escalation prevention."""
    current_user = get_current_user()
    if not current_user:
        return api_error("User not found", 404)

    # Customers can only update their own profile; admin/staff can update others
    if not prevent_customer_idor(user_id, current_user):
        return api_error("Access forbidden: you cannot update another user's profile", 403)

    data = request.get_json() or {}
    user, error = UserService.update_user(user_id, data, current_user.role)
    if error:
        return api_error(error, 400)
    return api_response(data=user, message="User updated successfully", status_code=200)


@user_bp.route("/<int:user_id>/toggle-active", methods=["PUT"])
@jwt_required()
@roles_required("admin", "staff")
def toggle_user_active(user_id):
    """Activates or deactivates an account."""
    current_user = get_current_user()
    user, error = UserService.toggle_user_active(user_id, current_user.id, current_user.role)
    if error:
        return api_error(error, 400)
    return api_response(data=user, message="User active status updated", status_code=200)

