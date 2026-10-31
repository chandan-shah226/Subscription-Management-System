"""
Routes Package
==============
Exports all API Blueprints for application factory registration.
"""

from routes.auth_routes import auth_bp
from routes.user_routes import user_bp
from routes.product_routes import product_bp
from routes.plan_routes import plan_bp
from routes.quotation_routes import quotation_bp
from routes.subscription_routes import subscription_bp

__all__ = [
    "auth_bp",
    "user_bp",
    "product_bp",
    "plan_bp",
    "quotation_bp",
    "subscription_bp",
]
