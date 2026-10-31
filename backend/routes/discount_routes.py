"""
Discount API Routes (Module 5)
==============================
Admin-only CRUD and rule management for discounts,
plus eligibility preview endpoint for checkout/invoice calculation.
"""

from decimal import Decimal
from flask import Blueprint, request, jsonify

from middleware.auth_middleware import (
    get_current_user,
    auth_required,
    roles_required
)
from services.discount_service import (
    create_discount,
    update_discount,
    toggle_discount_status,
    get_discount,
    list_discounts,
    get_discount_statistics,
    find_eligible_discounts,
    select_best_discount
)
from models import Discount

discount_bp = Blueprint("discounts", __name__, url_prefix="/api/discounts")


@discount_bp.route("", methods=["GET"])
@roles_required("admin")
def get_all_discounts():
    """Admin-only: lists all discount rules with search, status filters, and pagination."""
    filters = {
        "search": request.args.get("search", ""),
        "discount_type": request.args.get("discount_type", ""),
        "status": request.args.get("status", ""),
        "scope": request.args.get("scope", ""),
        "page": request.args.get("page", 1),
        "limit": request.args.get("limit", request.args.get("per_page", 20))
    }
    result = list_discounts(filters)
    return jsonify({
        "success": True,
        "discounts": result["discounts"],
        "data": result["discounts"],
        "pagination": result["pagination"]
    }), 200


@discount_bp.route("/stats", methods=["GET"])
@roles_required("admin")
def get_discount_stats():
    """Admin-only: returns aggregate KPI statistics for the discount dashboard."""
    stats = get_discount_statistics()
    return jsonify({
        "success": True,
        "stats": stats,
        "data": stats
    }), 200


@discount_bp.route("/<int:discount_id>", methods=["GET"])
@roles_required("admin")
def get_single_discount(discount_id):
    """Admin-only: retrieves full configuration and redemption metrics for a discount rule."""
    try:
        discount = get_discount(discount_id)
        d_dict = discount.to_dict(include_products=True)
        return jsonify({
            "success": True,
            "discount": d_dict,
            "data": d_dict
        }), 200
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 404


@discount_bp.route("", methods=["POST"])
@roles_required("admin")
def create_discount_rule():
    """Admin-only: defines and creates a new discount rule."""
    data = request.get_json() or {}
    current_user = get_current_user()

    try:
        discount = create_discount(data, creator=current_user)
        return jsonify({
            "success": True,
            "message": f"Discount rule '{discount.code}' created successfully.",
            "discount": discount.to_dict(include_products=True)
        }), 201
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@discount_bp.route("/<int:discount_id>", methods=["PUT"])
@roles_required("admin")
def update_discount_rule(discount_id):
    """Admin-only: updates an existing discount rule."""
    data = request.get_json() or {}
    current_user = get_current_user()

    try:
        discount = update_discount(discount_id, data, user=current_user)
        return jsonify({
            "success": True,
            "message": f"Discount rule '{discount.code}' updated successfully.",
            "discount": discount.to_dict(include_products=True)
        }), 200
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@discount_bp.route("/<int:discount_id>/toggle", methods=["POST"])
@roles_required("admin")
def toggle_status(discount_id):
    """Admin-only: activates or deactivates a discount rule."""
    data = request.get_json() or {}
    is_active = data.get("is_active")

    try:
        discount = toggle_discount_status(discount_id, is_active=is_active)
        state_str = "activated" if discount.is_active else "deactivated"
        return jsonify({
            "success": True,
            "message": f"Discount rule '{discount.code}' {state_str} successfully.",
            "discount": discount.to_dict()
        }), 200
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@discount_bp.route("/preview", methods=["POST"])
@auth_required
def preview_discount_eligibility():
    """
    Evaluates discount eligibility and calculates potential savings.
    Accessible to all authenticated users (Admin, Staff, Customer).
    """
    data = request.get_json() or {}
    subtotal_raw = data.get("subtotal", 0)
    try:
        subtotal = Decimal(str(subtotal_raw))
    except Exception:
        return jsonify({"success": False, "error": "Invalid subtotal amount"}), 400

    quantity = int(data.get("quantity", 1))
    product_ids = data.get("product_ids")
    code = (data.get("code") or "").strip().upper()
    is_subscription = bool(data.get("is_subscription", False))

    if code:
        discount = Discount.query.filter_by(code=code).first()
        if not discount:
            return jsonify({
                "success": False,
                "eligible": False,
                "error": f"Discount code '{code}' does not exist."
            }), 404

        is_valid, reason = discount.is_eligible(
            subtotal=subtotal,
            quantity=quantity,
            product_ids=product_ids
        )

        if not is_valid:
            return jsonify({
                "success": True,
                "eligible": False,
                "reason": reason,
                "discount_amount": 0.0,
                "discount": discount.to_dict()
            }), 200

        benefit = discount.calculate_discount_amount(subtotal)
        return jsonify({
            "success": True,
            "eligible": True,
            "discount_amount": float(benefit),
            "discount": discount.to_dict()
        }), 200

    # If no code supplied, automatically determine the best eligible discount
    best_disc, best_amount = select_best_discount(
        subtotal=subtotal,
        quantity=quantity,
        product_ids=product_ids,
        is_subscription=is_subscription
    )

    if best_disc:
        return jsonify({
            "success": True,
            "has_discount": True,
            "best_discount": best_disc.to_dict(),
            "discount_amount": float(best_amount)
        }), 200
    else:
        return jsonify({
            "success": True,
            "has_discount": False,
            "best_discount": None,
            "discount_amount": 0.0
        }), 200
