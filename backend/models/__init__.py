"""
Models Package
==============
Defines database models and schemas using SQLAlchemy.
Exports all models for application-wide database operations.
"""

from flask_sqlalchemy import SQLAlchemy

# Shared SQLAlchemy database instance
db = SQLAlchemy()

# Import models to register them with the SQLAlchemy instance
from models.user import User, PasswordReset, UserPermission
from models.product import Product, ProductVariant
from models.plan import SubscriptionPlan, PlanProduct
from models.quotation import Quotation, QuotationItem
from models.subscription import Subscription, SubscriptionItem, SubscriptionAuditLog

__all__ = [
    "db",
    "User",
    "PasswordReset",
    "UserPermission",
    "Product",
    "ProductVariant",
    "SubscriptionPlan",
    "PlanProduct",
    "Quotation",
    "QuotationItem",
    "Subscription",
    "SubscriptionItem",
    "SubscriptionAuditLog",
]
