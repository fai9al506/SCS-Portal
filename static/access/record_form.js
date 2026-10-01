/* Single-record Access form engine (Master Data screens).
 * Mirrors Access: opens on a blank new record, record navigation bar, the record is saved
 * when the user leaves it (navigate / new / close), Esc undoes edits, Ctrl+- deletes,
 * Find (binoculars) searches the field that had focus before, the Search box finds as you type.
 */
function RecordForm(cfg) {
    const fields = cfg.fields;                       // [{attr, kind, options?}]
    let rows = cfg.rows;
    let pos = rows.length;                           // rows.length = the new (blank) record
    let dirty = false;
    let lastField = fields[0].attr;
    const el = attr => document.getElementById("f_" + attr);
    const nav = {
        first: document.getElementById("nav_first"), prev: document.getElementById("nav_prev"),
        next: document.getElementById("nav_next"), last: document.getElementById("nav_last"),
        add: document.getElementById("nav_new"), pos: document.getElementById("nav_pos"),
        search: document.getElementById("nav_search"),
    };

    function current() { return pos < rows.length ? rows[pos] : null; }

    function show() {
        const r = current();
        fields.forEach(f => { el(f.attr).value = r ? (r[f.attr] ?? "") : ""; });
        dirty = false;
        const n = rows.length;
        nav.pos.value = pos < n ? `${pos + 1} of ${n}` : `${n + 1} of ${n}`;
        nav.first.disabled = nav.prev.disabled = pos === 0;
        nav.next.disabled = pos >= n;
        nav.last.disabled = n === 0 || pos === n - 1;
    }

    function values() {
        const v = { _id: current() ? current()._id : null };
        fields.forEach(f => { v[f.attr] = el(f.attr).value; });
        return v;
    }

    function checkLists() {
        for (const f of fields) {
            if (f.kind === "customer" && el(f.attr).value && !cfg.options.customer.includes(el(f.attr).value)) {
                el(f.attr).focus();
                return "The text you entered isn't an item in the list.\n\nSelect an item from the list, or enter text that matches one of the listed items.";
            }
        }
        return null;
    }

    /* Save the record if it changed. Resolves true when it is safe to leave the record. */
    async function commit() {
        if (!dirty) return true;
        const listErr = checkLists();
        if (listErr) { await msgBox(listErr); return false; }
        try {
            const v = values();
            const res = await postJSON(cfg.saveUrl, v);
            rows = res.rows;
            dirty = false;
            const id = res.record._id;
            pos = rows.findIndex(r => r._id === id);
            return true;
        } catch (e) {
            await msgBox(e.message);
            return false;
        }
    }

    async function go(target) {
        if (!(await commit())) return;
        pos = Math.max(0, Math.min(target, rows.length));
        show();
    }

    // Navigation bar
    nav.first.onclick = () => go(0);
    nav.prev.onclick = () => go(pos - 1);
    nav.next.onclick = () => go(pos + 1);
    nav.last.onclick = () => go(rows.length - 1);
    nav.add.onclick = () => go(rows.length);
    nav.pos.addEventListener("keydown", e => {
        if (e.key !== "Enter") return;
        const n = parseInt(nav.pos.value, 10);
        if (n >= 1) go(n - 1); else show();
    });
    nav.pos.addEventListener("focus", () => nav.pos.select());

    // Search box: first record (from the top) with any field containing the text
    function search(from) {
        const q = nav.search.value.trim().toLowerCase();
        if (!q) return;
        for (let i = 0; i < rows.length; i++) {
            const k = (from + i) % rows.length;
            if (fields.some(f => String(display(rows[k], f)).toLowerCase().includes(q))) { go(k); return; }
        }
    }
    function display(r, f) {
        if (f.kind === "group") { const o = cfg.options.group.find(g => g[0] === r[f.attr]); return o ? o[1] : ""; }
        return r[f.attr] ?? "";
    }
    nav.search.addEventListener("input", () => search(0));
    nav.search.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); search(pos + 1); } });

    // Track edits and the last focused field (Access Screen.PreviousControl)
    fields.forEach(f => {
        el(f.attr).addEventListener("input", () => { dirty = true; });
        el(f.attr).addEventListener("change", () => { dirty = true; });
        el(f.attr).addEventListener("focus", () => { lastField = f.attr; });
    });

    // Buttons: Add Record (pencil), Find Record (binoculars)
    document.getElementById("btn_new").onclick = () => go(rows.length);
    document.getElementById("btn_find").onclick = () => findDialog();

    document.addEventListener("keydown", async e => {
        if (e.target.closest(".msg-overlay")) return;
        if (e.key === "Escape" && dirty) { e.preventDefault(); show(); }
        else if (e.key === "PageDown") { e.preventDefault(); go(pos + 1); }
        else if (e.key === "PageUp") { e.preventDefault(); go(pos - 1); }
        else if (e.ctrlKey && (e.key === "-" || e.key === "Subtract")) { e.preventDefault(); deleteRecord(); }
        else if (e.ctrlKey && e.key.toLowerCase() === "f") { e.preventDefault(); findDialog(); }
    });

    async function deleteRecord() {
        const r = current();
        if (!r) { if (dirty) show(); return; }
        const ans = await msgBox("You are about to delete 1 record(s).\n\nIf you click Yes, you won't be able to undo this Delete operation.\nAre you sure you want to delete these records?",
            { buttons: ["Yes", "No"], icon: "warn" });
        if (ans !== "Yes") return;
        try {
            const res = await postJSON(cfg.deleteUrl, { _id: r._id });
            rows = res.rows;
            pos = Math.min(pos, rows.length);
            show();
        } catch (e) { await msgBox(e.message); }
    }

    // Find and Replace (Find tab) on the field that had focus before
    function findDialog() {
        const fieldDef = fields.find(f => f.attr === lastField) || fields[0];
        const label = document.querySelector(`label[for="f_${fieldDef.attr}"]`);
        const ov = document.createElement("div");
        ov.className = "msg-overlay";
        ov.innerHTML = `<div class="msg-box" style="width:380px"><div class="msg-title">Find and Replace</div>
            <div class="find-grid">
              <span>Find What:</span><input type="text" id="fd_what">
              <span>Look In:</span><select id="fd_in"><option value="field">Current field</option><option value="doc">Current document</option></select>
              <span>Match:</span><select id="fd_match"><option value="whole">Whole Field</option><option value="any">Any Part of Field</option><option value="start">Start of Field</option></select>
            </div>
            <div class="msg-actions"><button id="fd_next">Find Next</button><button id="fd_cancel">Cancel</button></div></div>`;
        document.body.appendChild(ov);
        ov.querySelector("#fd_in option").textContent = "Current field" + (label ? ` (${label.textContent})` : "");
        const what = ov.querySelector("#fd_what");
        what.focus();
        const matches = (r, f, q, m) => {
            const v = String(display(r, f)).toLowerCase();
            return m === "whole" ? v === q : m === "start" ? v.startsWith(q) : v.includes(q);
        };
        ov.querySelector("#fd_next").onclick = async () => {
            const q = what.value.trim().toLowerCase();
            if (!q) return;
            const m = ov.querySelector("#fd_match").value;
            const flds = ov.querySelector("#fd_in").value === "field" ? [fieldDef] : fields;
            for (let i = 1; i <= rows.length; i++) {
                const k = (Math.min(pos, rows.length - 1) + i) % rows.length;
                if (flds.some(f => matches(rows[k], f, q, m))) { await go(k); return; }
            }
            await msgBox("Microsoft Access finished searching the records. The search item was not found.", { icon: "info" });
            what.focus();
        };
        const done = () => ov.remove();
        ov.querySelector("#fd_cancel").onclick = done;
        ov.addEventListener("keydown", e => {
            if (e.key === "Escape") done();
            if (e.key === "Enter") ov.querySelector("#fd_next").click();
        });
    }

    // Closing the window saves the record first, like Access
    window.scsBeforeClose = commit;

    show();
    el(fields[0].attr).focus();
}
