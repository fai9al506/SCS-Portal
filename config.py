import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///dev.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # App
    APP_URL = os.environ.get("APP_URL", "https://scs.modernpetro.com")
    TIMEZONE = "Asia/Riyadh"

    # Session security
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") != "development"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 28800  # 8 hours
