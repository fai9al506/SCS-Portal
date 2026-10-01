"""Screen engine: Access forms, continuous forms, reports and Outlook drafts defined as data.

Each section module (screens_po.py, screens_sf.py, …) registers its screens here:

    form("new_po", title="New PO", model=ShipmentsStatus, controls=[...], ...)   # single-record form
    grid("updation_eta", title="Shipments Status", model=ShipmentsStatus, columns=[...], ...)  # continuous form
    report("incoming_shipments", title=..., template=..., data=fn)               # print preview
    eml("payment_request", build=fn)                                              # Outlook draft (.eml)

blueprints/screens.py serves them; static/access/single_form.js and grid_form.js run them.

Control / column keys
---------------------
type     label | text | number | date | combo | select | check | calc | button | box | line | memo
field    bound model attribute (Access field name)      name   key of a calc value
x y w h  position in px (Access twips / 15)              style  extra CSS
fmt      standard | dollar | percent | int               locked / bold / align / bg / color / tab / tip
options  list or fn(params) -> [value] or [[value, col2, …]] (combo/select)   limit  LimitToList
after    name of a hook run after the value changes (Access AfterUpdate)
action   (buttons) {"do": new|delete|close|find|save|open|eml|hook|js|print, …} — see single_form.js
"""
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, Numeric, String, cast, or_
from sqlalchemy import inspect as sa_inspect

from extensions import db
from services import fmt

REGISTRY = {}


class ScreenError(Exception):
    """A message to show the user in an Access-style message box."""


def form(key, **d):
    d.update(kind="form", key=key)
    d.setdefault("open_at", "new")
    d.setdefault("allow_add", True)
    d.setdefault("allow_delete", True)
    d.setdefault("allow_edit", True)
    d.setdefault("nav", True)
    REGISTRY[key] = d
    return d


def grid(key, **d):
    d.update(kind="grid", key=key)
    d.setdefault("allow_add", False)
    d.setdefault("allow_delete", True)
    d.setdefault("allow_edit", True)
    d.setdefault("nav", True)
    d.setdefault("row_h", 24)
    REGISTRY[key] = d
    return d


def report(key, **d):
    d.update(kind="report", key=key)
    REGISTRY[key] = d
    return d


def pdf(key, **d):
    """build(params) -> (filename, pdf bytes)."""
    d.update(kind="pdf", key=key)
    REGISTRY[key] = d
    return d


def eml(key, **d):
    d.update(kind="eml", key=key)
    REGISTRY[key] = d
    return d


# ── helpers ───────────────────────────────────────────────────────────

def pk_attr(model):
    mapper = sa_inspect(model)
    return mapper.get_property_by_column(mapper.primary_key[0]).key


def column(model, attr):
    return getattr(model, attr).property.columns[0]


def bound(items):
    """Controls/columns bound to a model field."""
    return [c for c in items if c.get("field")]


def items_of(d):
    return d.get("controls") or d.get("columns") or []


def options_of(c, params):
    opts = c.get("options")
    if callable(opts):
        opts = opts(params)
    return [o if isinstance(o, (list, tuple)) else [o] for o in (opts or [])]


def record_dict(model, row):
    """Typed values of every mapped attribute of a row, plus `_id`."""
    rec = {p.key: getattr(row, p.key) for p in sa_inspect(model).column_attrs}
    rec["_id"] = getattr(row, pk_attr(model))
    return rec


def display(v, f=None):
    out = fmt.fmt_value(v, f)
    return out


def serialize(d, rec, params):
    """Values sent to the browser: formatted bound fields and calc values."""
    out = {"_id": rec.get("_id")}
    calc = d["calc"](rec, params) if d.get("calc") else {}
    for c in items_of(d):
        if c.get("field"):
            v = rec.get(c["field"])
            out[c["field"]] = bool(v) if c.get("type") == "check" else display(v, c.get("fmt"))
        elif c.get("name") and c["name"] in calc:
            out[c["name"]] = display(calc[c["name"]], c.get("fmt"))
    for k, v in calc.items():           # calc values not shown by a control (used by actions)
        out.setdefault(k, display(v))
    return out


def parse_value(model, c, raw):
    col = column(model, c["field"])
    t = col.type
    if c.get("type") == "check" or isinstance(t, Boolean):
        return bool(raw)
    if raw is None:
        return None
    if isinstance(raw, str):
        raw = raw.strip() if not isinstance(t, String) else raw.rstrip()
    if isinstance(t, (Date, DateTime)):
        return fmt.parse_date(raw)
    if isinstance(t, Integer):
        v = fmt.parse_number(raw)
        return None if v is None else int(round(v))
    if isinstance(t, (Numeric, Float)):
        return fmt.parse_number(raw)
    s = str(raw)
    if s.strip() == "":
        return None
    if getattr(t, "length", None) and len(s) > t.length:
        raise ScreenError("The field is too small to accept the amount of data you attempted to add. "
                          "Try inserting or pasting less data.")
    return s


def parse_values(d, values, params, only_editable=True):
    """Browser values -> typed values for the bound, editable controls present in `values`."""
    model = d["model"]
    typed = {}
    for c in bound(items_of(d)):
        f = c["field"]
        if f not in values or (only_editable and c.get("locked") and not c.get("unlockable")):
            continue
        if column(model, f).computed is not None:
            continue
        v = parse_value(model, c, values[f])
        if c.get("limit") and v not in (None, "") and c.get("type") in ("combo", "select"):
            allowed = {str(o[0]) for o in options_of(c, params)}
            if str(v) not in allowed:
                raise ScreenError("The text you entered isn't an item in the list.\n\n"
                                  "Select an item from the list, or enter text that matches one of the listed items.")
        typed[f] = v
    return typed


def loose_rec(d, values, params, base=None):
    """Typed record from browser values for live calculations; bad values become None."""
    rec = dict(base or {})
    for c in bound(items_of(d)):
        f = c["field"]
        if f in values:
            try:
                rec[f] = parse_value(d["model"], c, values[f])
            except Exception:
                rec[f] = None
    return rec


def ordered_ids(d, params):
    model = d["model"]
    q = d["query"](params) if d.get("query") else model.query.order_by(getattr(model, pk_attr(model)))
    return [getattr(r, pk_attr(model)) for r in q.with_entities(getattr(model, pk_attr(model)))]


def search_ids(d, params, q, fields=None, match="any"):
    """IDs (in form order) of records where any of `fields` matches q (Access Search box / Find)."""
    model = d["model"]
    fields = fields or [c["field"] for c in bound(items_of(d))]
    base = d["query"](params) if d.get("query") else model.query.order_by(getattr(model, pk_attr(model)))
    conds = []
    ql = q.lower()
    for f in fields:
        col = getattr(model, f)
        t = column(model, f).type
        if isinstance(t, (Date, DateTime)):
            try:
                dv = fmt.parse_date(q)
                conds.append(col == dv)
            except fmt.ParseError:
                pass
            continue
        expr = db.func.lower(cast(col, String))
        if match == "whole":
            conds.append(expr == ql)
        elif match == "start":
            conds.append(expr.like(ql + "%"))
        else:
            conds.append(expr.like("%" + ql + "%"))
    if not conds:
        return []
    return [getattr(r, pk_attr(model)) for r in base.filter(or_(*conds)).with_entities(getattr(model, pk_attr(model)))]


def window_size(d):
    if d.get("win"):
        return d["win"]
    head = d.get("header", {}).get("h", 0)
    foot = d.get("footer", {}).get("h", 0)
    body = d.get("detail", {}).get("h", 300) if d["kind"] == "form" else d.get("body_h", 420)
    nav = 24 if d.get("nav") else 0
    return d.get("width", 400) + 2 + (18 if d["kind"] == "grid" else 0), 31 + head + body + foot + nav + 2


def today():
    return date.today()


def now():
    return datetime.now()
