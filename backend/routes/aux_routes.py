"""
Auxiliary Data Routes
=====================
Provides live backend data endpoints for Customers, Subscriptions,
Products, and Discounts to power dynamic dropdowns and line item selection.
"""

from flask import Blueprint, request, jsonify
from models import User, Subscription, Product, Discount
from middleware.auth_middleware import get_current_user

aux_bp = Blueprint("aux", __name__)


@aux_bp.route("/customers", methods=["GET"])
def get_customers():
    """Returns list of active customers for invoice dropdowns."""
    current_user = get_current_user()
    if current_user and current_user.role == "customer":
        customers = [current_user]
    else:
        customers = User.query.filter_by(is_active=True).all()

    return jsonify({
        "success": True,
        "customers": [
            {
                "id": c.id,
                "full_name": c.full_name,
                "email": c.email,
                "company_name": c.company_name or "",
                "role": c.role
            }
            for c in customers
        ]
    }), 200


@aux_bp.route("/subscriptions", methods=["GET"])
def get_subscriptions():
    """Returns subscriptions, optionally filtered by customer_id."""
    current_user = get_current_user()
    query = Subscription.query

    if current_user and current_user.role == "customer":
        query = query.filter_by(customer_id=current_user.id)
    elif request.args.get("customer_id"):
        query = query.filter_by(customer_id=int(request.args.get("customer_id")))

    subscriptions = query.all()
    return jsonify({
        "success": True,
        "subscriptions": [
            {
                "id": s.id,
                "subscription_number": s.subscription_number,
                "customer_id": s.customer_id,
                "customer_name": s.customer.full_name if s.customer else "",
                "plan_name": s.plan.name if s.plan else "Custom",
                "status": s.status,
                "billing_frequency": s.billing_frequency,
                "next_billing_date": s.next_billing_date.isoformat() if s.next_billing_date else None,
                "tax_rate": float(s.tax_rate or 0.0),
                "discount_amount": float(s.discount_amount or 0.0)
            }
            for s in subscriptions
        ]
    }), 200


@aux_bp.route("/products", methods=["GET"])
def get_products():
    """Returns active products and their variants for invoice line item selection."""
    products = Product.query.filter_by(is_active=True).all()
    return jsonify({
        "success": True,
        "products": [p.to_dict() for p in products]
    }), 200


@aux_bp.route("/discounts", methods=["GET"])
def get_discounts():
    """Returns active discount codes and rules."""
    discounts = Discount.query.filter_by(is_active=True).all()
    return jsonify({
        "success": True,
        "discounts": [d.to_dict() for d in discounts]
    }), 200
