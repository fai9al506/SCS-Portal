"""Routes for the screen engine (services/screens.py): forms, continuous forms, reports, emails, PDFs."""
from flask import Blueprint, Response, abort, jsonify, render_template, request
from flask_login import current_user, login_required

from extensions import db
from services import fmt
from services.audit import log_action
from services.eml import build_eml
from services.screens import (
    REGISTRY, ScreenError, items_of, loose_rec, options_of, ordered_ids, parse_values, pk_attr,
    record_dict, search_ids, serialize, window_size,
)

bp = Blueprint("screens", __name__)


def _get(key, kind):
    d = REGISTRY.get(key)
    if not d or d["kind"] != kind:
        abort(404)
    return d


def _params():
    p = request.args.to_dict()
    if request.is_json:
        p.update((request.get_json(silent=True) or {}).get("params") or {})
    return p


def _client_items(d, params):
    """Controls/columns for the browser: no callables, options evaluated."""
    out = []
    for c in items_of(d):
        cc = {k: v for k, v in c.items() if not callable(v) and k != "options"}
        if c.get("type") in ("combo", "select") or c.get("options") is not None:
            cc["options"] = [[str(x) if x is not None else "" for x in o] for o in options_of(c, params)]
        out.append(cc)
    return out


def _model_defaults(model):
    """Access table defaults (e.g. Status "Ordered", EntryDate today) for a new record."""
    vals = {}
    for prop in db.inspect(model).column_attrs:
        col = prop.columns[0]
        if col.default is not None and col.computed is None and not col.primary_key:
            arg = col.default.arg
            vals[prop.key] = arg(None) if callable(arg) else arg
    return vals


def _new_rec(d, params):
    rec = _model_defaults(d["model"])
    if d.get("defaults"):
        rec.update(d["defaults"](params))
    rec["_id"] = None
    return rec


def _err(e):
    db.session.rollback()
    return jsonify(error=str(e)), 400


def _save(d, params, data):
    model = d["model"]
    rid = data.get("_id")
    values = data.get("values") or {}
    row = db.session.get(model, rid) if rid else None
    if rid and row is None:
        raise ScreenError("The record was deleted by another user.")
    if row is None and not d.get("allow_add", True):
        raise ScreenError("You can't add records here.")
    if row is not None and not d.get("allow_edit", True):
        raise ScreenError("This recordset is not updateable.")
    typed = parse_values(d, values, params)
    before = record_dict(model, row) if row is not None else None
    merged = {**(before or _new_rec(d, params)), **typed}
    for f, label in (d.get("required") or {}).items():
        if merged.get(f) in (None, ""):
            raise ScreenError(f"You must enter a value in the '{label}' field.")
    if d.get("before_save"):
        d["before_save"](row, typed, params, merged)
    is_new = row is None
    if is_new:
        row = model()
        for k, v in _new_rec(d, params).items():
            if k != "_id" and v is not None:
                setattr(row, k, v)
        db.session.add(row)
    for k, v in typed.items():
        setattr(row, k, v)
    db.session.flush()
    if d.get("after_save"):
        d["after_save"](row, params, is_new)
    db.session.commit()
    after = record_dict(model, row)
    changed = {k: str(v) for k, v in after.items() if before is None or before.get(k) != v}
    log_action(current_user.id, "User", "create" if is_new else "update", model.__access_table__,
               after["_id"] if isinstance(after["_id"], int) else None,
               before={k: str(before.get(k)) for k in changed} if before else None, after=changed)
    return row


def _delete(d, params, rid):
    model = d["model"]
    if not d.get("allow_delete", True):
        raise ScreenError("You can't delete records here.")
    row = db.session.get(model, rid)
    if row is None:
        return
    if d.get("before_delete"):
        d["before_delete"](row, params)
    before = {k: str(v) for k, v in record_dict(model, row).items()}
    db.session.delete(row)
    db.session.commit()
    log_action(current_user.id, "User", "delete", model.__access_table__, rid if isinstance(rid, int) else None,
               before=before)


def _hook(d, name, params, data):
    """Run a screen hook. A hook gets (rec, params, row) and returns a dict:
    {"updates": {field: value}, "message": str, "open": {...}, "reload": bool, "close": bool}."""
    model = d["model"]
    rid = data.get("_id")
    row = db.session.get(model, rid) if rid else None
    base = record_dict(model, row) if row is not None else _new_rec(d, params)
    rec = loose_rec(d, data.get("values") or {}, params, base)
    res = d["hooks"][name](rec, params, row) or {}
    out = {k: v for k, v in res.items() if k != "updates"}
    if res.get("updates"):
        upd = {}
        cmap = {c.get("field"): c for c in items_of(d) if c.get("field")}
        for k, v in res["updates"].items():
            c = cmap.get(k, {})
            upd[k] = bool(v) if c.get("type") == "check" else fmt.fmt_value(v, c.get("fmt"))
        out["updates"] = upd
    return out


# ── single-record forms ───────────────────────────────────────────────

@bp.route("/f/<key>")
@login_required
def form_page(key):
    d = _get(key, "form")
    params = _params()
    ids = ordered_ids(d, params)
    if params.get("id"):
        start = next((i for i, x in enumerate(ids) if str(x) == params["id"]), len(ids))
    elif d["open_at"] == "last" and ids:
        start = len(ids) - 1
    elif d["open_at"] == "first" and ids:
        start = 0
    else:
        start = len(ids) if d.get("allow_add", True) else 0
    if start < len(ids):
        rec = serialize(d, record_dict(d["model"], db.session.get(d["model"], ids[start])), params)
    else:
        rec = serialize(d, _new_rec(d, params), params)
    cfg = dict(key=key, ids=ids, pos=start, rec=rec, params=params, items=_client_items(d, params),
               allow_add=d.get("allow_add", True), allow_delete=d.get("allow_delete", True),
               allow_edit=d.get("allow_edit", True), locked_mode=d.get("locked_mode", False),
               nav=d.get("nav", True))
    return render_template("access/single_form.html", d=d, cfg=cfg, items=cfg["items"])


@bp.route("/f/<key>/rec/<rid>")
@login_required
def form_rec(key, rid):
    d = _get(key, "form")
    params = _params()
    if rid == "new":
        return jsonify(rec=serialize(d, _new_rec(d, params), params))
    row = db.session.get(d["model"], int(rid))
    if row is None:
        return jsonify(error="The record was deleted by another user."), 404
    return jsonify(rec=serialize(d, record_dict(d["model"], row), params))


@bp.route("/f/<key>/save", methods=["POST"])
@login_required
def form_save(key):
    d = _get(key, "form")
    params = _params()
    try:
        row = _save(d, params, request.get_json())
    except (ScreenError, fmt.ParseError) as e:
        return _err(e)
    rec = serialize(d, record_dict(d["model"], row), params)
    return jsonify(rec=rec, ids=ordered_ids(d, params))


@bp.route("/f/<key>/delete", methods=["POST"])
@login_required
def form_delete(key):
    d = _get(key, "form")
    params = _params()
    try:
        _delete(d, params, request.get_json()["_id"])
    except ScreenError as e:
        return _err(e)
    return jsonify(ids=ordered_ids(d, params))


@bp.route("/f/<key>/calc", methods=["POST"])
@login_required
def form_calc(key):
    d = _get(key, "form")
    params = _params()
    data = request.get_json()
    row = db.session.get(d["model"], data["_id"]) if data.get("_id") else None
    base = record_dict(d["model"], row) if row is not None else _new_rec(d, params)
    rec = loose_rec(d, data.get("values") or {}, params, base)
    out = serialize(d, rec, params)
    calc_names = {c["name"] for c in items_of(d) if c.get("name")}
    return jsonify(calc={k: v for k, v in out.items() if k in calc_names or k not in data.get("values", {})})


@bp.route("/f/<key>/hook/<name>", methods=["POST"])
@login_required
def form_hook(key, name):
    d = _get(key, "form")
    try:
        res = _hook(d, name, _params(), request.get_json())
        db.session.commit()
    except (ScreenError, fmt.ParseError) as e:
        return _err(e)
    return jsonify(res)


@bp.route("/f/<key>/search")
@login_required
def form_search(key):
    d = _get(key, "form")
    params = _params()
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify(id=None)
    field = request.args.get("field")
    ids = search_ids(d, params, q, [field] if field else None, request.args.get("match", "any"))
    order = ordered_ids(d, params)
    start = int(request.args.get("from", 0))
    hits = set(ids)
    for i in range(len(order)):
        k = (start + i) % len(order) if order else 0
        if order and order[k] in hits:
            return jsonify(id=order[k], pos=k)
    return jsonify(id=None)


# ── continuous forms ──────────────────────────────────────────────────

def _grid_rows(d, params):
    q = d["query"](params) if d.get("query") else d["model"].query
    return [serialize(d, record_dict(d["model"], r), params) for r in q.all()]


@bp.route("/g/<key>")
@login_required
def grid_page(key):
    d = _get(key, "grid")
    params = _params()
    cfg = dict(key=key, rows=_grid_rows(d, params), params=params, items=_client_items(d, params),
               allow_add=d.get("allow_add"), allow_delete=d.get("allow_delete", True),
               allow_edit=d.get("allow_edit", True), row_h=d["row_h"], nav=d.get("nav", True),
               copy=d.get("copy", False), blank_row=d.get("blank_row", False))
    return render_template("access/grid_form.html", d=d, cfg=cfg, items=cfg["items"])


@bp.route("/g/<key>/rows")
@login_required
def grid_rows(key):
    d = _get(key, "grid")
    return jsonify(rows=_grid_rows(d, _params()))


@bp.route("/g/<key>/save", methods=["POST"])
@login_required
def grid_save(key):
    d = _get(key, "grid")
    params = _params()
    try:
        row = _save(d, params, request.get_json())
    except (ScreenError, fmt.ParseError) as e:
        return _err(e)
    return jsonify(row=serialize(d, record_dict(d["model"], row), params))


@bp.route("/g/<key>/copy", methods=["POST"])
@login_required
def grid_copy(key):
    """Access 'Add new item': select record, copy, go to new record, paste."""
    d = _get(key, "grid")
    params = _params()
    model = d["model"]
    src = db.session.get(model, request.get_json()["_id"]) or abort(404)
    fields = d.get("copy_fields") or [c["field"] for c in items_of(d) if c.get("field")]
    vals = {f: getattr(src, f) for f in fields
            if db.inspect(model).get_property(f).columns[0].computed is None}
    if d.get("before_copy"):
        vals = d["before_copy"](src, vals, params) or vals
    row = model(**vals)
    db.session.add(row)
    db.session.commit()
    log_action(current_user.id, "User", "copy", model.__access_table__, getattr(row, pk_attr(model)),
               after={k: str(v) for k, v in vals.items()})
    return jsonify(row=serialize(d, record_dict(model, row), params))


@bp.route("/g/<key>/delete", methods=["POST"])
@login_required
def grid_delete(key):
    d = _get(key, "grid")
    try:
        _delete(d, _params(), request.get_json()["_id"])
    except ScreenError as e:
        return _err(e)
    return jsonify(ok=True)


@bp.route("/g/<key>/hook/<name>", methods=["POST"])
@login_required
def grid_hook(key, name):
    d = _get(key, "grid")
    try:
        res = _hook(d, name, _params(), request.get_json())
        db.session.commit()
    except (ScreenError, fmt.ParseError) as e:
        return _err(e)
    return jsonify(res)


@bp.route("/g/<key>/calc", methods=["POST"])
@login_required
def grid_calc(key):
    d = _get(key, "grid")
    params = _params()
    data = request.get_json()
    row = db.session.get(d["model"], data["_id"]) if data.get("_id") else None
    base = record_dict(d["model"], row) if row is not None else {}
    rec = loose_rec(d, data.get("values") or {}, params, base)
    return jsonify(calc=serialize(d, rec, params))


# ── reports, emails, PDFs, custom pages ───────────────────────────────

@bp.route("/r/<key>")
@login_required
def report_page(key):
    d = _get(key, "report")
    params = _params()
    try:
        ctx = d["data"](params) if d.get("data") else {}
    except ScreenError as e:
        return render_template("access/report_message.html", message=str(e))
    return render_template(d["template"], d=d, params=params, fmt=fmt, **ctx)


@bp.route("/e/<key>")
@login_required
def eml_download(key):
    d = _get(key, "eml")
    try:
        m = d["build"](_params())
    except ScreenError as e:
        return Response(str(e), status=400, mimetype="text/plain")
    data = build_eml(m["to"], m.get("cc"), m["subject"], m["html"], m.get("attachments"))
    safe = "".join(ch if ch.isalnum() or ch in " -_#.()" else "_" for ch in m["subject"])[:120] or "email"
    log_action(current_user.id, "User", "email_draft", key, None, after={"subject": m["subject"], "to": m["to"]})
    return Response(data, mimetype="message/rfc822",
                    headers={"Content-Disposition": f'attachment; filename="{safe}.eml"'})


@bp.route("/pdf/<key>")
@login_required
def pdf_download(key):
    d = _get(key, "pdf")
    try:
        name, data = d["build"](_params())
    except ScreenError as e:
        return Response(str(e), status=400, mimetype="text/plain")
    inline = request.args.get("inline") == "1"
    return Response(data, mimetype="application/pdf",
                    headers={"Content-Disposition": f'{"inline" if inline else "attachment"}; filename="{name}"'})


@bp.route("/screen-size/<key>")
@login_required
def screen_size(key):
    d = REGISTRY.get(key) or abort(404)
    w, h = window_size(d)
    return jsonify(w=w, h=h, title=d.get("title", key))
