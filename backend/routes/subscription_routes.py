"""
Subscription API Endpoints
==========================
Routes for subscription lifecycle operations, quotation conversion, direct creation,
pausing, resuming, renewing, and audit log inspection.
"""

from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from middleware.auth import api_response, api_error, get_current_user, prevent_customer_idor
from services.subscription_service import SubscriptionService

subscription_bp = Blueprint("subscriptions", __name__, url_prefix="/api/subscriptions")


@subscription_bp.route("", methods=["GET"])
@jwt_required()
def list_subscriptions():
    """Lists subscriptions. Customers see only their own subscriptions; staff/admin see all."""
    current_user = get_current_user()
    status_filter = request.args.get("status")
    customer_id = current_user.id if current_user.role == "customer" else request.args.get("customer_id", type=int)

    subs = SubscriptionService.list_subscriptions(customer_id=customer_id, status_filter=status_filter)
    return api_response(data=subs, status_code=200)


@subscription_bp.route("/<int:subscription_id>", methods=["GET"])
@jwt_required()
def get_subscription(subscription_id):
    """Retrieves subscription details, items, and full audit logs."""
    current_user = get_current_user()
    subscription = SubscriptionService.get_subscription_by_id(subscription_id)
    if not subscription:
        return api_error("Subscription not found", 404)

    # Prevent Customer IDOR
    if not prevent_customer_idor(subscription["customer_id"], current_user):
        return api_error("Access forbidden: you can only view your own subscriptions", 403)

    return api_response(data=subscription, status_code=200)


@subscription_bp.route("", methods=["POST"])
@jwt_required()
def create_subscription():
    """Creates a direct subscription with line items."""
    current_user = get_current_user()
    data = request.get_json() or {}

    if current_user.role == "customer":
        data["customer_id"] = current_user.id

    subscription, error = SubscriptionService.create_direct_subscription(data, user_id=current_user.id)
    if error:
        return api_error(error, 400)
    return api_response(data=subscription, message="Subscription created and activated successfully", status_code=201)


@subscription_bp.route("/convert-quotation/<int:quotation_id>", methods=["POST"])
@jwt_required()
def convert_quotation(quotation_id):
    """Converts a confirmed quotation into an active subscription."""
    current_user = get_current_user()
    subscription, error = SubscriptionService.convert_quotation_to_subscription(quotation_id, user_id=current_user.id)
    if error:
        return api_error(error, 400)
    return api_response(data=subscription, message="Quotation converted to subscription successfully", status_code=201)


@subscription_bp.route("/<int:subscription_id>/pause", methods=["POST"])
@jwt_required()
def pause_subscription(subscription_id):
    """Pauses an active subscription if plan policy permits."""
    current_user = get_current_user()
    sub_data = SubscriptionService.get_subscription_by_id(subscription_id)
    if not sub_data:
        return api_error("Subscription not found", 404)

    if not prevent_customer_idor(sub_data["customer_id"], current_user):
        return api_error("Access forbidden", 403)

    subscription, error = SubscriptionService.pause_subscription(subscription_id, user_id=current_user.id)
    if error:
        return api_error(error, 400)
    return api_response(data=subscription, message="Subscription paused successfully", status_code=200)


@subscription_bp.route("/<int:subscription_id>/resume", methods=["POST"])
@jwt_required()
def resume_subscription(subscription_id):
    """Resumes a paused subscription."""
    current_user = get_current_user()
    sub_data = SubscriptionService.get_subscription_by_id(subscription_id)
    if not sub_data:
        return api_error("Subscription not found", 404)

    if not prevent_customer_idor(sub_data["customer_id"], current_user):
        return api_error("Access forbidden", 403)

    subscription, error = SubscriptionService.resume_subscription(subscription_id, user_id=current_user.id)
    if error:
        return api_error(error, 400)
    return api_response(data=subscription, message="Subscription resumed successfully", status_code=200)


@subscription_bp.route("/<int:subscription_id>/renew", methods=["POST"])
@jwt_required()
def renew_subscription(subscription_id):
    """Renews a subscription and advances its billing schedule."""
    current_user = get_current_user()
    sub_data = SubscriptionService.get_subscription_by_id(subscription_id)
    if not sub_data:
        return api_error("Subscription not found", 404)

    if not prevent_customer_idor(sub_data["customer_id"], current_user):
        return api_error("Access forbidden", 403)

    subscription, error = SubscriptionService.renew_subscription(subscription_id, user_id=current_user.id)
    if error:
        return api_error(error, 400)
    return api_response(data=subscription, message="Subscription renewed successfully", status_code=200)


@subscription_bp.route("/<int:subscription_id>/close", methods=["POST"])
@jwt_required()
def close_subscription(subscription_id):
    """Closes/terminates a subscription."""
    current_user = get_current_user()
    sub_data = SubscriptionService.get_subscription_by_id(subscription_id)
    if not sub_data:
        return api_error("Subscription not found", 404)

    if not prevent_customer_idor(sub_data["customer_id"], current_user):
        return api_error("Access forbidden", 403)

    subscription, error = SubscriptionService.close_subscription(subscription_id, user_id=current_user.id)
    if error:
        return api_error(error, 400)
    return api_response(data=subscription, message="Subscription closed successfully", status_code=200)

