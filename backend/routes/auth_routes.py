"""
Authentication API Endpoints
============================
Routes for customer registration, login, token refresh, current user profile,
and secure password reset.
"""

from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from middleware.auth import api_response, api_error, get_current_user
from services.auth_service import AuthService

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/register", methods=["POST"])
def register():
    """Customer registration endpoint."""
    data = request.get_json() or {}
    user, error = AuthService.register_customer(data)
    if error:
        return api_error(error, 400)
    return api_response(
        data=user.to_dict(include_permissions=True),
        message="Account registered successfully. You can now log in.",
        status_code=201
    )


@auth_bp.route("/login", methods=["POST"])
def login():
    """Authenticates credentials and returns JWT access + refresh tokens."""
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")

    auth_data, error = AuthService.authenticate_user(email, password)
    if error:
        return api_error(error, 401)
    return api_response(data=auth_data, message="Login successful", status_code=200)


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def get_me():
    """Retrieves the currently authenticated user profile and permissions."""
    user = get_current_user()
    if not user:
        return api_error("User not found", 404)
    if not user.is_active:
        return api_error("User account is inactive", 403)
    return api_response(data=user.to_dict(include_permissions=True), status_code=200)


@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    """Initiates a secure password reset request."""
    data = request.get_json() or {}
    email = data.get("email", "")
    res, error = AuthService.request_password_reset(email)
    if error:
        return api_error(error, 400)
    return api_response(data=res, message=res["message"], status_code=200)


@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    """Resets password using a verified single-use token."""
    data = request.get_json() or {}
    token = data.get("token", "")
    new_password = data.get("new_password", "")
    confirm_password = data.get("confirm_password", "")

    success, error = AuthService.reset_password(token, new_password, confirm_password)
    if error:
        return api_error(error, 400)
    return api_response(message="Password has been reset successfully. You can now log in.", status_code=200)

