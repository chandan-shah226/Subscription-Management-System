"""
Configuration settings for the Subscription Management System.
Handles environment-based configurations for development, testing, and production.
"""

import os
from datetime import timedelta
from pathlib import Path

# Base directory of the backend application
BASE_DIR = Path(__file__).resolve().parent

# Instance directory located in the project root
INSTANCE_DIR = BASE_DIR.parent / "instance"


class Config:
    """Base configuration with shared default parameters."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-brightloop-subscription-system-2026-safe-32-bytes")
    
    # SQLite Database Configuration (default: instance/subscription_system.db)
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{INSTANCE_DIR / 'subscription_system.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Flask-JWT-Extended Configuration
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-jwt-secret-key-brightloop-subscription-system-2026-safe-32-bytes")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=2)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    # Pagination & Cache Configuration
    DEFAULT_PER_PAGE = 20
    MAX_PER_PAGE = 100
    CACHE_TTL_SECONDS = 60

    # Razorpay Payment Gateway Configuration (Module 6: Test Mode)
    RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "rzp_test_placeholder_key")
    RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "placeholder_secret")
    RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "placeholder_webhook_secret")
    RAZORPAY_MODE = os.environ.get("RAZORPAY_MODE", "test")


class DevelopmentConfig(Config):
    """Configuration for local development."""
    DEBUG = True


class TestingConfig(Config):
    """Configuration for automated test suites."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    RAZORPAY_KEY_ID = "rzp_test_testkey123"
    RAZORPAY_KEY_SECRET = "testsecret1234567890"
    RAZORPAY_WEBHOOK_SECRET = "testwebhooksecret123"
    RAZORPAY_MODE = "test"


class ProductionConfig(Config):
    """Configuration for production deployment."""
    DEBUG = False
    # Ensure sensitive secrets are overridden via environment variables in production


# Configuration dictionary mapping for easy selection
config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
