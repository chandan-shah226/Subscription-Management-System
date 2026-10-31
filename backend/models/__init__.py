"""
Models Package
==============
Defines database models and schemas using SQLAlchemy.

Developers can create modular model files here (e.g., user.py, product.py,
plan.py, quotation.py, invoice.py, payment.py) and expose them through this file.
"""

from flask_sqlalchemy import SQLAlchemy

# Shared SQLAlchemy database instance
db = SQLAlchemy()

__all__ = ["db"]

