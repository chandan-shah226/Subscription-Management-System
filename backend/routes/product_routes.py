"""
Product and Variant API Endpoints
=================================
Routes for managing the product catalog, variant additions, and pricing rules.
"""

from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from middleware.auth import api_response, api_error, roles_required
from services.product_service import ProductService

product_bp = Blueprint("products", __name__, url_prefix="/api/products")


@product_bp.route("", methods=["GET"])
@jwt_required()
def list_products():
    """Lists products with optional active_only, product_type, and search filters."""
    active_only = request.args.get("active_only", "false").lower() in ["true", "1"]
    product_type = request.args.get("product_type")
    search = request.args.get("search")

    products = ProductService.list_products(active_only=active_only, product_type=product_type, search=search)
    return api_response(data=products, status_code=200)


@product_bp.route("/<int:product_id>", methods=["GET"])
@jwt_required()
def get_product(product_id):
    """Retrieves a single product with variants."""
    product = ProductService.get_product_by_id(product_id)
    if not product:
        return api_error("Product not found", 404)
    return api_response(data=product, status_code=200)


@product_bp.route("", methods=["POST"])
@jwt_required()
@roles_required("admin", "staff")
def create_product():
    """Creates a new product with optional initial variants."""
    data = request.get_json() or {}
    product, error = ProductService.create_product(data)
    if error:
        return api_error(error, 400)
    return api_response(data=product, message="Product created successfully", status_code=201)


@product_bp.route("/<int:product_id>", methods=["PUT"])
@jwt_required()
@roles_required("admin", "staff")
def update_product(product_id):
    """Updates an existing product."""
    data = request.get_json() or {}
    product, error = ProductService.update_product(product_id, data)
    if error:
        return api_error(error, 400)
    return api_response(data=product, message="Product updated successfully", status_code=200)


@product_bp.route("/<int:product_id>/toggle-active", methods=["PUT"])
@jwt_required()
@roles_required("admin", "staff")
def toggle_product_active(product_id):
    """Toggles product active status."""
    product, error = ProductService.toggle_product_active(product_id)
    if error:
        return api_error(error, 400)
    return api_response(data=product, message="Product status updated", status_code=200)


@product_bp.route("/<int:product_id>/variants", methods=["POST"])
@jwt_required()
@roles_required("admin", "staff")
def add_variant(product_id):
    """Adds a variant to a product."""
    data = request.get_json() or {}
    variant, error = ProductService.add_variant(product_id, data)
    if error:
        return api_error(error, 400)
    return api_response(data=variant, message="Variant added successfully", status_code=201)


@product_bp.route("/variants/<int:variant_id>", methods=["PUT"])
@jwt_required()
@roles_required("admin", "staff")
def update_variant(variant_id):
    """Updates an existing variant."""
    data = request.get_json() or {}
    variant, error = ProductService.update_variant(variant_id, data)
    if error:
        return api_error(error, 400)
    return api_response(data=variant, message="Variant updated successfully", status_code=200)

