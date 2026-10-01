"""Admin-editable settings (decision B7). Sections declare their defaults with `default()`;
missing keys are created on first use so admins can see and change them."""
from extensions import db
from models import AppSetting

DEFAULTS = {}


def default(key, value, description=""):
    DEFAULTS[key] = (str(value), description)


def get(key, cast=str):
    row = AppSetting.query.filter_by(Key=key).first()
    if row is None:
        value, desc = DEFAULTS.get(key, ("", ""))
        row = AppSetting(Key=key, Value=value, Description=desc)
        db.session.add(row)
        db.session.commit()
    v = row.Value
    if cast is float:
        return float(v or 0)
    if cast is int:
        return int(float(v or 0))
    return v or ""


def ensure_all():
    """Create any missing settings with their defaults (called at startup)."""
    have = {r.Key for r in AppSetting.query.all()}
    for k, (v, desc) in DEFAULTS.items():
        if k not in have:
            db.session.add(AppSetting(Key=k, Value=v, Description=desc))
    db.session.commit()
