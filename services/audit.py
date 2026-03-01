from extensions import db
from models import AuditLog, utcnow


def log_action(actor_id, actor_type, action, entity_type, entity_id=None, before=None, after=None):
    """Record an action in the audit log."""
    entry = AuditLog(
        actor_id=actor_id,
        actor_type=actor_type,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_json=before,
        after_json=after,
        timestamp=utcnow(),
    )
    db.session.add(entry)
    db.session.commit()
