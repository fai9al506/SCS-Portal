/* Continuous Access form: one row per record, each row editable in place.
 * A row is saved when the user moves to another row or closes the window (like Access).
 * Header buttons act on the current row: {"do": "copy"} = Access "Add new item" (duplicate the row),
 * "delete", "close", "save", "reload", "open"/"eml"/"pdf"/"hook"/"js" (same as single_form.js).
 */
function GridForm(cfg) {
    const base = `/g/${cfg.key}`;
    const items = cfg.items.filter(c => !c.sec);
    const bound = items.filter(c => c.field);
    const calcNames = items.filter(c => c.name && c.type !== "button").map(c => c.name);
    const box = document.getElementById("grid_rows");
    const tpl = document.getElementById("row_tpl");
    let rows = cfg.rows, cur = -1, dirty = new Set();

    function el(i) { return box.children[i]; }
    function inp(i, k) { const r = el(i); return r && r.querySelector(`[data-key="${CSS.escape(k)}"]`); }

    function setCell(i, k, v) {
        const e = inp(i, k);
        if (!e) return;
        if (e.type === "checkbox") e.checked = !!v; else e.value = v ?? "";
        const c = items.find(x => (x.field || x.name) === k);
        if (c && c.cond) applyCondStyle(e, c.cond, e.value);
    }
    function rowValues(i) {
        const v = {};
        bound.forEach(c => { if (!c.locked) { const e = inp(i, c.field); if (e) v[c.field] = e.type === "checkbox" ? e.checked : e.value; } });
        return v;
    }
    function rowData(i) { return Object.assign({}, rows[i], rowValues(i)); }

    function paint(i) {
        const r = rows[i];
        bound.forEach(c => setCell(i, c.field, r[c.field]));
        calcNames.forEach(n => setCell(i, n, r[n]));
        el(i).classList.toggle("alt", i % 2 === 1);
    }

    function makeRow(i) {
        const node = tpl.content.firstElementChild.cloneNode(true);
        node.querySelectorAll("[id]").forEach(e => e.removeAttribute("id"));
        node.querySelectorAll("[data-key]").forEach(e => {
            const k = e.dataset.key;
            const c = items.find(x => (x.field || x.name) === k);
            e.addEventListener("focus", () => setCurrent(indexOf(node)));
            if (!c || !c.field) return;
            e.addEventListener("input", () => { dirty.add(rows[indexOf(node)]._id); if (c.cond) applyCondStyle(e, c.cond, e.value); });
            e.addEventListener("change", async () => {
                const i2 = indexOf(node);
                dirty.add(rows[i2]._id);
                if (c.after) await rowHook(i2, c.after, {});
                else if (calcNames.length) await recalc(i2);
            });
        });
        node.querySelectorAll("[data-action]").forEach(b => b.addEventListener("click", async () => {
            const i2 = indexOf(node);
            await setCurrent(i2);
            await doAction(JSON.parse(b.dataset.action), i2);
        }));
        node.addEventListener("mousedown", () => setCurrent(indexOf(node)));
        return node;
    }
    const indexOf = node => Array.prototype.indexOf.call(box.children, node);

    function render() {
        box.innerHTML = "";
        rows.forEach((r, i) => { box.appendChild(makeRow(i)); paint(i); });
        updateNav();
    }

    async function commitRow(i) {
        if (i < 0 || i >= rows.length || !dirty.has(rows[i]._id)) return true;
        try {
            const res = await postJSON(`${base}/save`, { _id: rows[i]._id, values: rowValues(i), params: cfg.params });
            dirty.delete(rows[i]._id);
            rows[i] = res.row;
            paint(i);
            return true;
        } catch (e) {
            await msgBox(e.message);
            const first = el(i).querySelector("input:not([readonly]),select");
            if (first) first.focus();
            return false;
        }
    }

    let switching = false;
    async function setCurrent(i) {
        if (i === cur || switching) return true;
        switching = true;
        const ok = await commitRow(cur);
        switching = false;
        if (!ok) return false;
        if (el(cur)) el(cur).classList.remove("current");
        cur = i;
        if (el(cur)) el(cur).classList.add("current");
        updateNav();
        return true;
    }

    async function recalc(i) {
        try {
            const res = await postJSON(`${base}/calc`, { _id: rows[i]._id, values: rowValues(i), params: cfg.params });
            calcNames.forEach(n => { if (n in res.calc) setCell(i, n, res.calc[n]); });
        } catch (e) { /* ignore */ }
    }

    async function rowHook(i, name, a) {
        if (a.confirm && (await msgBox(a.confirm, { buttons: ["Yes", "No"], icon: "question" })) !== "Yes") return;
        if (a.save && !(await commitRow(i))) return;
        let res;
        try { res = await postJSON(`${base}/hook/${name}`, { _id: i >= 0 ? rows[i]._id : null, values: i >= 0 ? rowValues(i) : {}, params: cfg.params }); }
        catch (e) { await msgBox(e.message); return; }
        if (res.updates && i >= 0) {
            Object.entries(res.updates).forEach(([k, v]) => setCell(i, k, v));
            dirty.add(rows[i]._id);
            if (calcNames.length) await recalc(i);
        }
        if (res.save && i >= 0) await commitRow(i);
        if (res.message) await msgBox(res.message, { icon: res.icon || "info" });
        if (res.download) download(fill(res.download, i));
        if (res.open) openScreen(res.open, i);
        if (res.reload) await reload();
        if (res.close) closeForm();
    }

    function fill(url, i) {
        const r = i >= 0 ? rowData(i) : {};
        Object.entries(cfg.params).forEach(([k, v]) => { if (!(k in r)) r[k] = v; });
        return url.replace(/\{(\w+)\}/g, (_, k) => encodeURIComponent(r[k] ?? ""));
    }
    function openScreen(a, i) {
        const open = window.parent !== window && window.parent.SCSWindows ? window.parent.SCSWindows.open : (u) => window.open(u, "_blank");
        open(fill(a.url, i), a.title || "", a.w || 600, a.h || 400, null, a.prompt);
    }
    function download(url) {
        const a = document.createElement("a");
        a.href = url; a.download = "";
        document.body.appendChild(a); a.click(); a.remove();
    }

    async function reload() {
        await commitRow(cur);
        const res = await (await fetch(`${base}/rows?${new URLSearchParams(cfg.params)}`)).json();
        rows = res.rows; dirty.clear(); cur = -1;
        render();
    }

    async function doAction(a, i) {
        i = i ?? cur;
        switch (a.do) {
            case "copy": {
                if (i < 0) { if (rows.length) i = rows.length - 1; else return; }
                if (!(await commitRow(i))) return;
                try {
                    const res = await postJSON(`${base}/copy`, { _id: rows[i]._id, params: cfg.params });
                    rows.push(res.row);
                    box.appendChild(makeRow(rows.length - 1));
                    paint(rows.length - 1);
                    await setCurrent(rows.length - 1);
                    const f = el(rows.length - 1).querySelector("input:not([readonly]),select");
                    if (f) f.focus();
                    el(rows.length - 1).scrollIntoView({ block: "nearest" });
                } catch (e) { await msgBox(e.message); }
                break;
            }
            case "delete": {
                if (!cfg.allow_delete || i < 0) return;
                const ans = await msgBox("You are about to delete 1 record(s).\n\nIf you click Yes, you won't be able to undo this Delete operation.\nAre you sure you want to delete these records?", { buttons: ["Yes", "No"] });
                if (ans !== "Yes") return;
                try {
                    await postJSON(`${base}/delete`, { _id: rows[i]._id, params: cfg.params });
                    dirty.delete(rows[i]._id);
                    rows.splice(i, 1);
                    cur = -1;
                    render();
                } catch (e) { await msgBox(e.message); }
                break;
            }
            case "close": if (await commitRow(cur)) closeForm(); break;
            case "save": await commitRow(cur); break;
            case "reload": await reload(); break;
            case "open": if (a.save && !(await commitRow(i))) return; openScreen(a, i); if (a.close_self) closeForm(); break;
            case "eml": case "pdf": if (a.save && !(await commitRow(i))) return; download(fill(a.url, i)); break;
            case "hook": await rowHook(i, a.name, a); break;
            case "js": if (window[a.fn]) await window[a.fn](api, a, i); break;
            case "print": window.print(); break;
        }
    }

    // header / footer buttons act on the current row
    document.querySelectorAll(".grid-head [data-action], .sec:not(.grid-head) [data-action]").forEach(b => {
        if (b.closest(".grow")) return;
        b.addEventListener("click", () => doAction(JSON.parse(b.dataset.action)));
    });

    // navigation bar
    const nav = n => document.getElementById("nav_" + n);
    function updateNav() {
        if (!cfg.nav) return;
        const n = rows.length, p = cur < 0 ? 0 : cur;
        document.getElementById("nav_pos").value = n ? `${p + 1} of ${n}` : `0 of 0`;
        nav("first").disabled = nav("prev").disabled = p <= 0;
        nav("next").disabled = nav("last").disabled = p >= n - 1;
        nav("new").disabled = !cfg.copy;
    }
    async function goRow(i) {
        if (!rows.length) return;
        i = Math.max(0, Math.min(i, rows.length - 1));
        if (!(await setCurrent(i))) return;
        const f = el(i).querySelector("input:not([readonly]),select,input");
        if (f) f.focus();
        el(i).scrollIntoView({ block: "nearest" });
    }
    if (cfg.nav) {
        nav("first").onclick = () => goRow(0);
        nav("prev").onclick = () => goRow((cur < 0 ? 0 : cur) - 1);
        nav("next").onclick = () => goRow((cur < 0 ? 0 : cur) + 1);
        nav("last").onclick = () => goRow(rows.length - 1);
        nav("new").onclick = () => doAction({ do: "copy" });
        const np = document.getElementById("nav_pos");
        np.addEventListener("focus", () => np.select());
        np.addEventListener("keydown", e => { if (e.key === "Enter") goRow(parseInt(np.value, 10) - 1); });
        const ns = document.getElementById("nav_search");
        const search = from => {
            const q = ns.value.trim().toLowerCase();
            if (!q) return;
            for (let k = 0; k < rows.length; k++) {
                const i = (from + k) % rows.length;
                if (Object.values(rows[i]).some(v => String(v ?? "").toLowerCase().includes(q))) { goRow(i); ns.focus(); return; }
            }
        };
        ns.addEventListener("input", () => search(0));
        ns.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); search(cur + 1); } });
    }
    document.addEventListener("keydown", e => {
        if (e.target.closest(".msg-overlay")) return;
        if (e.key === "Escape" && cur >= 0 && dirty.has(rows[cur]._id)) { e.preventDefault(); dirty.delete(rows[cur]._id); paint(cur); }
        else if (e.ctrlKey && (e.key === "-" || e.key === "Subtract")) { e.preventDefault(); doAction({ do: "delete" }); }
        else if (e.key === "ArrowDown" && e.target.tagName === "INPUT" && !e.target.list) { e.preventDefault(); goRow(cur + 1); }
        else if (e.key === "ArrowUp" && e.target.tagName === "INPUT" && !e.target.list) { e.preventDefault(); goRow(cur - 1); }
    });

    window.scsBeforeClose = () => commitRow(cur);
    const api = { cfg, get rows() { return rows; }, get cur() { return cur; }, reload, doAction, rowData, setCell,
                  commitRow, goRow, markDirty: i => dirty.add(rows[i]._id) };
    window.grid = api;
    render();
    if (rows.length) goRow(0);
}
