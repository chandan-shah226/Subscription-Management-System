"""
Routes Package
==============
Exports all API Blueprints for application factory registration.
Includes Modules 1, 2, 3, 4 (Invoices & Billing), 5 (Discounts), 6 (Payments), and 7 (Finance).
"""

from routes.auth_routes import auth_bp
from routes.user_routes import user_bp
from routes.product_routes import product_bp
from routes.plan_routes import plan_bp
from routes.quotation_routes import quotation_bp
from routes.subscription_routes import subscription_bp
from routes.invoice_routes import invoice_bp
from routes.discount_routes import discount_bp
from routes.payment_routes import payment_bp
from routes.finance import bp as finance_bp

__all__ = [
    "auth_bp",
    "user_bp",
    "product_bp",
    "plan_bp",
    "quotation_bp",
    "subscription_bp",
    "invoice_bp",
    "discount_bp",
    "payment_bp",
    "finance_bp",
]
