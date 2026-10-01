import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///dev.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # App
    APP_URL = os.environ.get("APP_URL", "https://scs.modernpetro.com")
    TIMEZONE = "Asia/Riyadh"

    # Session security
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") != "development"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Like Access (DetectIdleTime): sign out after 30 min with no activity.
    # The session is refreshed on every request, so the 30 min counts from the last action.
    PERMANENT_SESSION_LIFETIME = 1800
