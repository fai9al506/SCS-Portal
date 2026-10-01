/* Single-record Access form (Default View = Single Form).
 * Like Access: the record is saved when the user leaves it (navigate, New, close, or a button
 * that saves first), Esc undoes edits, PageUp/PageDown move records, Ctrl+- deletes, Ctrl+F finds.
 * Button actions ({"do": ...}):
 *   new | delete | close | find | save | unlock
 *   open  {url, title, w, h, save, close_self, prompt}   open another screen in a popup window
 *   eml   {url, save}                                      download an Outlook draft
 *   pdf   {url, save}                                      download a PDF
 *   hook  {name, save, confirm}                            run a server hook (updates/message/open/reload/close)
 *   js    {fn}                                             window[fn](form)
 * URLs may contain {Field} placeholders, filled from the current record ({_id} = record ID).
 */
function SingleForm(cfg) {
    const base = `/f/${cfg.key}`;
    const qs = new URLSearchParams(cfg.params).toString();
    const items = cfg.items;
    let ids = cfg.ids, pos = cfg.pos, rec = cfg.rec, dirty = false, lastKey = null;
    let unlocked = !cfg.locked_mode;
    const ctl = k => document.getElementById("f_" + k);
    const bound = items.filter(c => c.field);
    const calcNames = items.filter(c => c.name && c.type !== "button").map(c => c.name);

    function setVal(k, v) {
        const e = ctl(k);
        if (!e) return;
        if (e.type === "checkbox") e.checked = !!v;
        else e.value = v ?? "";
        applyCond(k);
    }
    function getVal(k) {
        const e = ctl(k);
        if (!e) return undefined;
        return e.type === "checkbox" ? e.checked : e.value;
    }
    function applyCond(k) {
        const c = items.find(i => (i.field || i.name) === k);
        const e = ctl(k);
        if (c && c.cond && e) applyCondStyle(e, c.cond, e.value);
    }
    function values() {
        const v = {};
        bound.forEach(c => { if (!c.locked || unlocked && c.unlockable) v[c.field] = getVal(c.field); });
        return v;
    }
    function current() { return Object.assign({}, rec, values()); }

    function show(r) {
        rec = r;
        bound.forEach(c => setVal(c.field, r[c.field]));
        calcNames.forEach(n => setVal(n, r[n]));
        dirty = false;
        updateNav();
        if (window.onFormRecord) window.onFormRecord(api);
    }

    function updateNav() {
        if (!cfg.nav) return;
        const n = ids.length;
        const p = document.getElementById("nav_pos");
        p.value = pos < n ? `${pos + 1} of ${n}` : `${n + 1} of ${n}`;
        nav("first").disabled = nav("prev").disabled = pos === 0;
        nav("next").disabled = pos >= n || (pos === n - 1 && !cfg.allow_add);
        nav("last").disabled = n === 0 || pos === n - 1;
        nav("new").disabled = !cfg.allow_add;
    }
    const nav = n => document.getElementById("nav_" + n);

    async function load(p) {
        p = Math.max(0, Math.min(p, cfg.allow_add ? ids.length : ids.length - 1));
        const id = p < ids.length ? ids[p] : "new";
        const r = await (await fetch(`${base}/rec/${id}?${qs}`)).json();
        if (r.error) { await msgBox(r.error); return; }
        pos = p;
        show(r.rec);
    }

    async function commit() {
        if (!dirty) return true;
        try {
            const res = await postJSON(`${base}/save`, { _id: rec._id, values: values(), params: cfg.params });
            ids = res.ids;
            const i = ids.indexOf(res.rec._id);
            pos = i >= 0 ? i : Math.min(pos, ids.length);
            show(res.rec);
            return true;
        } catch (e) { await msgBox(e.message); return false; }
    }

    async function go(p) { if (await commit()) await load(p); }

    async function recalc() {
        if (!calcNames.length) return;
        try {
            const res = await postJSON(`${base}/calc`, { _id: rec._id, values: values(), params: cfg.params });
            calcNames.forEach(n => { if (n in res.calc) setVal(n, res.calc[n]); });
        } catch (e) { /* ignore live-calc errors */ }
    }

    async function runHook(name, opts) {
        opts = opts || {};
        if (opts.confirm && (await msgBox(opts.confirm, { buttons: ["Yes", "No"], icon: "question" })) !== "Yes") return;
        if (opts.save && !(await commit())) return;
        let res;
        try { res = await postJSON(`${base}/hook/${name}`, { _id: rec._id, values: values(), params: cfg.params }); }
        catch (e) { await msgBox(e.message); return; }
        await handleResult(res);
    }

    async function handleResult(res) {
        if (res.updates) {
            Object.entries(res.updates).forEach(([k, v]) => setVal(k, v));
            dirty = true;
            await recalc();
        }
        if (res.save) await commit();
        if (res.message) await msgBox(res.message, { icon: res.icon || "info" });
        if (res.download) download(res.download);
        if (res.open) openScreen(res.open);
        if (res.reload) { ids = res.ids || ids; await load(res.pos ?? pos); }
        if (res.close) { dirty = false; closeForm(); }
    }

    function fill(url) {
        const r = current();
        return url.replace(/\{(\w+)\}/g, (_, k) => encodeURIComponent(r[k] ?? ""));
    }

    function openScreen(a) {
        const url = fill(a.url);
        const open = window.parent !== window && window.parent.SCSWindows
            ? window.parent.SCSWindows.open : (u) => window.open(u, "_blank");
        open(url, a.title || "", a.w || 600, a.h || 400, null, a.prompt);
    }

    function download(url) {
        const a = document.createElement("a");
        a.href = fill(url);
        a.download = "";
        document.body.appendChild(a);
        a.click();
        a.remove();
    }

    async function doAction(a) {
        switch (a.do) {
            case "new": if (cfg.allow_add) await go(ids.length); break;
            case "delete": await deleteRecord(); break;
            case "close": if (await commit()) closeForm(); break;
            case "find": findDialog(); break;
            case "save": await commit(); break;
            case "unlock":
                unlocked = true;
                items.forEach(c => { if (c.unlockable && ctl(c.field)) { ctl(c.field).readOnly = false; ctl(c.field).disabled = false; ctl(c.field).classList.remove("locked"); } });
                break;
            case "open":
                if (a.save && !(await commit())) return;
                openScreen(a);
                if (a.close_self) { closeForm(); }
                break;
            case "eml": case "pdf":
                if (a.save && !(await commit())) return;
                if (a.check && !rec._id) { await msgBox(a.check); return; }
                download(a.url);
                break;
            case "hook": await runHook(a.name, a); break;
            case "js": if (window[a.fn]) await window[a.fn](api, a); break;
            case "print": window.print(); break;
        }
    }

    async function deleteRecord() {
        if (!cfg.allow_delete) return;
        if (!rec._id) { if (dirty) show(rec); return; }
        const ans = await msgBox("You are about to delete 1 record(s).\n\nIf you click Yes, you won't be able to undo this Delete operation.\nAre you sure you want to delete these records?", { buttons: ["Yes", "No"] });
        if (ans !== "Yes") return;
        try {
            const res = await postJSON(`${base}/delete`, { _id: rec._id, params: cfg.params });
            ids = res.ids;
            dirty = false;
            await load(Math.min(pos, ids.length));
        } catch (e) { await msgBox(e.message); }
    }

    function findDialog() {
        const key = lastKey || (bound[0] && bound[0].field);
        const c = items.find(i => i.field === key) || bound[0];
        openFindDialog(c ? (c.label || c.field) : "", async (q, scope, match) => {
            const p = new URLSearchParams(cfg.params);
            p.set("q", q); p.set("match", match); p.set("from", pos + 1);
            if (scope === "field" && c) p.set("field", c.field);
            const r = await (await fetch(`${base}/search?${p}`)).json();
            if (r.id == null) return false;
            await go(r.pos);
            return true;
        });
    }

    // events
    bound.concat(items.filter(c => c.name)).forEach(c => {
        const e = ctl(c.field || c.name);
        if (!e) return;
        e.addEventListener("focus", () => { if (c.field) lastKey = c.field; });
        if (!c.field) return;
        e.addEventListener("input", () => { dirty = true; applyCond(c.field); });
        e.addEventListener("change", async () => {
            dirty = true;
            if (c.after) await runHook(c.after, {});
            else await recalc();
            if (window.onFieldChange) window.onFieldChange(api, c.field);
        });
    });
    document.querySelectorAll("[data-action]").forEach(b => b.addEventListener("click", () => doAction(JSON.parse(b.dataset.action))));
    if (cfg.nav) {
        nav("first").onclick = () => go(0);
        nav("prev").onclick = () => go(pos - 1);
        nav("next").onclick = () => go(pos + 1);
        nav("last").onclick = () => go(ids.length - 1);
        nav("new").onclick = () => doAction({ do: "new" });
        const np = document.getElementById("nav_pos");
        np.addEventListener("focus", () => np.select());
        np.addEventListener("keydown", e => { if (e.key === "Enter") { const n = parseInt(np.value, 10); if (n >= 1) go(n - 1); } });
        const ns = document.getElementById("nav_search");
        const search = async (from) => {
            if (!ns.value.trim()) return;
            const p = new URLSearchParams(cfg.params); p.set("q", ns.value.trim()); p.set("from", from);
            const r = await (await fetch(`${base}/search?${p}`)).json();
            if (r.id != null) await go(r.pos);
        };
        let t;
        ns.addEventListener("input", () => { clearTimeout(t); t = setTimeout(() => search(0), 300); });
        ns.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); search(pos + 1); } });
    }
    document.addEventListener("keydown", e => {
        if (e.target.closest(".msg-overlay")) return;
        if (e.key === "Escape" && dirty) { e.preventDefault(); show(rec); }
        else if (e.key === "PageDown" && cfg.nav) { e.preventDefault(); go(pos + 1); }
        else if (e.key === "PageUp" && cfg.nav) { e.preventDefault(); go(pos - 1); }
        else if (e.ctrlKey && (e.key === "-" || e.key === "Subtract")) { e.preventDefault(); deleteRecord(); }
        else if (e.ctrlKey && e.key.toLowerCase() === "f") { e.preventDefault(); findDialog(); }
        else if (e.ctrlKey && e.key.toLowerCase() === "s") { e.preventDefault(); commit(); }
    });

    window.scsBeforeClose = commit;
    const api = { cfg, commit, go, load, setVal, getVal, current, doAction, runHook, handleResult, openScreen,
                  download, get rec() { return rec; }, get pos() { return pos; }, markDirty: () => { dirty = true; } };
    window.form = api;
    show(rec);
    const first = items.find(c => c.field && !c.locked && c.type !== "calc");
    if (first && ctl(first.field)) ctl(first.field).focus();
}

/* Access Find and Replace dialog. search(q, scope, match) resolves true when found. */
function openFindDialog(fieldLabel, search) {
    const ov = document.createElement("div");
    ov.className = "msg-overlay";
    ov.innerHTML = `<div class="msg-box" style="width:380px"><div class="msg-title">Find and Replace</div>
        <div class="find-grid">
          <span>Find What:</span><input type="text" id="fd_what">
          <span>Look In:</span><select id="fd_in"><option value="field"></option><option value="doc">Current document</option></select>
          <span>Match:</span><select id="fd_match"><option value="whole">Whole Field</option><option value="any">Any Part of Field</option><option value="start">Start of Field</option></select>
        </div>
        <div class="msg-actions"><button id="fd_next">Find Next</button><button id="fd_cancel">Cancel</button></div></div>`;
    document.body.appendChild(ov);
    ov.querySelector("#fd_in option").textContent = "Current field" + (fieldLabel ? ` (${fieldLabel})` : "");
    const what = ov.querySelector("#fd_what");
    what.focus();
    ov.querySelector("#fd_next").onclick = async () => {
        const q = what.value.trim();
        if (!q) return;
        const found = await search(q, ov.querySelector("#fd_in").value, ov.querySelector("#fd_match").value);
        if (!found) { await msgBox("Microsoft Access finished searching the records. The search item was not found.", { icon: "info" }); what.focus(); }
    };
    ov.querySelector("#fd_cancel").onclick = () => ov.remove();
    ov.addEventListener("keydown", e => { if (e.key === "Escape") ov.remove(); if (e.key === "Enter") ov.querySelector("#fd_next").click(); });
}

/* Access conditional formatting. rules: [{op: lt|le|gt|ge|eq|ne|between|empty|notempty, a, b, style}] */
function applyCondStyle(el, rules, raw) {
    el.style.fontWeight = el.dataset.baseWeight ?? (el.dataset.baseWeight = el.style.fontWeight || "");
    el.style.color = el.dataset.baseColor ?? (el.dataset.baseColor = el.style.color || "");
    el.style.backgroundColor = el.dataset.baseBg ?? (el.dataset.baseBg = el.style.backgroundColor || "");
    const s = String(raw ?? "").trim();
    const n = parseFloat(s.replace(/[,$%()]/g, ""));
    for (const r of rules) {
        let hit = false;
        switch (r.op) {
            case "lt": hit = s !== "" && n < r.a; break;
            case "le": hit = s !== "" && n <= r.a; break;
            case "gt": hit = s !== "" && n > r.a; break;
            case "ge": hit = s !== "" && n >= r.a; break;
            case "between": hit = s !== "" && n >= r.a && n <= r.b; break;
            case "eq": hit = s.toLowerCase() === String(r.a).toLowerCase(); break;
            case "ne": hit = s.toLowerCase() !== String(r.a).toLowerCase(); break;
            case "empty": hit = s === ""; break;
            case "notempty": hit = s !== ""; break;
        }
        if (hit) {
            (r.style || "").split(";").forEach(p => {
                const [k, v] = p.split(":").map(x => x && x.trim());
                if (k === "bold") el.style.fontWeight = "bold";
                else if (k) el.style.setProperty(k, v);
            });
            break;   // Access applies the first matching rule
        }
    }
}
