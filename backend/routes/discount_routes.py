"""
Discount API Endpoints
======================
Routes for managing discount rules (Admin) and validating discounts on invoices/quotes.
"""

from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from middleware.auth import api_response, api_error, roles_required
from services.discount_service import DiscountService

discount_bp = Blueprint("discounts", __name__, url_prefix="/api/discounts")


@discount_bp.route("", methods=["GET"])
@jwt_required()
def list_discounts():
    """Lists discount rules."""
    active_only = request.args.get("active_only", "false").lower() in ["true", "1"]
    discounts = DiscountService.list_discounts(active_only=active_only)
    return api_response(data=discounts, status_code=200)


@discount_bp.route("", methods=["POST"])
@jwt_required()
@roles_required("admin")
def create_discount():
    """Admin-only: Creates a new discount rule."""
    data = request.get_json() or {}
    discount, error = DiscountService.create_discount(data)
    if error:
        return api_error(error, 400)
    return api_response(data=discount, message="Discount rule created successfully", status_code=201)


@discount_bp.route("/<int:discount_id>/toggle", methods=["POST"])
@jwt_required()
@roles_required("admin")
def toggle_discount(discount_id):
    """Admin-only: Toggles active status of a discount rule."""
    discount, error = DiscountService.toggle_status(discount_id)
    if error:
        return api_error(error, 400)
    status_msg = "activated" if discount["is_active"] else "deactivated"
    return api_response(data=discount, message=f"Discount {status_msg} successfully", status_code=200)


@discount_bp.route("/validate", methods=["POST"])
@jwt_required()
def validate_discount():
    """Validates coupon code against order amount or seat count."""
    data = request.get_json() or {}
    code = data.get("code")
    amount = data.get("amount", 0)
    quantity = data.get("quantity", 1)

    res, error = DiscountService.validate_code(code=code, amount=amount, quantity=quantity)
    if error:
        return api_error(error, 400)
    return api_response(data=res, message="Discount code is valid", status_code=200)
