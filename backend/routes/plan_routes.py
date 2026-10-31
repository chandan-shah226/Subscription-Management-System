"""
Subscription Plan API Endpoints
===============================
Routes for managing subscription plans, billing frequencies, and lifecycle policies.
"""

from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from middleware.auth import api_response, api_error, roles_required
from services.plan_service import PlanService

plan_bp = Blueprint("plans", __name__, url_prefix="/api/plans")


@plan_bp.route("", methods=["GET"])
@jwt_required()
def list_plans():
    """Lists subscription plans with optional availability and search filtering."""
    active_only = request.args.get("active_only", "false").lower() in ["true", "1"]
    available_only = request.args.get("available_only", "false").lower() in ["true", "1"]
    search = request.args.get("search")

    plans = PlanService.list_plans(active_only=active_only, available_only=available_only, search=search)
    return api_response(data=plans, status_code=200)


@plan_bp.route("/<int:plan_id>", methods=["GET"])
@jwt_required()
def get_plan(plan_id):
    """Retrieves a single subscription plan."""
    plan = PlanService.get_plan_by_id(plan_id)
    if not plan:
        return api_error("Plan not found", 404)
    return api_response(data=plan, status_code=200)


@plan_bp.route("", methods=["POST"])
@jwt_required()
@roles_required("admin", "staff")
def create_plan():
    """Creates a new subscription plan."""
    data = request.get_json() or {}
    plan, error = PlanService.create_plan(data)
    if error:
        return api_error(error, 400)
    return api_response(data=plan, message="Subscription plan created successfully", status_code=201)


@plan_bp.route("/<int:plan_id>", methods=["PUT"])
@jwt_required()
@roles_required("admin", "staff")
def update_plan(plan_id):
    """Updates an existing subscription plan."""
    data = request.get_json() or {}
    plan, error = PlanService.update_plan(plan_id, data)
    if error:
        return api_error(error, 400)
    return api_response(data=plan, message="Subscription plan updated successfully", status_code=200)


@plan_bp.route("/<int:plan_id>/toggle-active", methods=["PUT"])
@jwt_required()
@roles_required("admin", "staff")
def toggle_plan_active(plan_id):
    """Toggles subscription plan active status."""
    plan, error = PlanService.toggle_plan_active(plan_id)
    if error:
        return api_error(error, 400)
    return api_response(data=plan, message="Plan status updated", status_code=200)

