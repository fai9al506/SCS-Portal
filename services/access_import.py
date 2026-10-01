"""Load an Access export (tools/export_access.py) into the SCS tables.

Replaces ALL rows of every SCS table with the export's rows, so the portal = Access.
Users and the audit log are not touched.
"""
import gzip
import json
from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, Float, insert, text

from extensions import db
from models import ACCESS_FIELDS


def _convert(value, column):
    if value is None:
        return None
    t = column.type
    if isinstance(t, DateTime):
        return datetime.fromisoformat(value)
    if isinstance(t, Date):
        return datetime.fromisoformat(value).date()
    if isinstance(t, Boolean):
        return bool(value)
    if isinstance(t, Integer):
        return int(value)
    if isinstance(t, (Numeric, Float)):
        return value
    return str(value)


def load_export(fileobj):
    """Read a .json.gz (or plain .json) export from a file object."""
    raw = fileobj.read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


def import_access_data(data):
    """Replace every SCS table with the rows in `data`. Returns {access_table: row_count}."""
    tables = data["tables"]
    missing = [m.__access_table__ for m in ACCESS_FIELDS if m.__access_table__ not in tables]
    if missing:
        raise ValueError(f"Export is missing tables: {', '.join(missing)}")

    counts = {}
    for model, fields in ACCESS_FIELDS.items():
        attr_col = {attr: getattr(model, attr).property.columns[0] for attr in fields.values()}
        writable = {name: attr for name, attr in fields.items() if attr_col[attr].computed is None}
        # Core insert keyed by column name: an empty Access value stays NULL (the ORM would apply
        # Python defaults instead, e.g. VAT 0 or today's EntryDate).
        rows = [
            {attr_col[attr].name: _convert(row.get(name), attr_col[attr]) for name, attr in writable.items()}
            for row in tables[model.__access_table__]
        ]
        db.session.execute(model.__table__.delete())
        if rows:
            db.session.execute(insert(model.__table__), rows)
        counts[model.__access_table__] = len(rows)

        # Keep Postgres auto-numbers ahead of the imported Access IDs
        if db.engine.dialect.name == "postgresql":
            pk = list(model.__table__.primary_key.columns)[0]
            db.session.execute(text(
                f"SELECT setval(pg_get_serial_sequence('{model.__tablename__}', '{pk.name}'), "
                f"COALESCE((SELECT MAX({pk.name}) FROM {model.__tablename__}), 0) + 1, false)"
            ))
    db.session.commit()
    return counts
