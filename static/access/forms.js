/* Shared helpers for screens inside a popup window: Access message boxes and JSON posts. */
(function () {
    const csrf = () => (document.querySelector('meta[name="csrf-token"]') || {}).content;

    /* Access-style MsgBox. Resolves with the clicked button's label. */
    window.msgBox = function (text, opts) {
        opts = opts || {};
        const buttons = opts.buttons || ["OK"];
        const icon = { info: "ℹ️", warn: "⚠️", error: "⛔", question: "❓" }[opts.icon || "warn"];
        return new Promise(resolve => {
            const ov = document.createElement("div");
            ov.className = "msg-overlay";
            ov.innerHTML = '<div class="msg-box" role="alertdialog"><div class="msg-title"></div>' +
                '<div class="msg-body"><span class="msg-icon"></span><span class="msg-text"></span></div>' +
                '<div class="msg-actions"></div></div>';
            ov.querySelector(".msg-title").textContent = opts.title || "Microsoft Access";
            ov.querySelector(".msg-icon").textContent = icon;
            ov.querySelector(".msg-text").textContent = text;
            const actions = ov.querySelector(".msg-actions");
            buttons.forEach((b, i) => {
                const btn = document.createElement("button");
                btn.textContent = b;
                btn.onclick = () => { ov.remove(); resolve(b); };
                actions.appendChild(btn);
                if (i === 0) setTimeout(() => btn.focus(), 0);
            });
            ov.addEventListener("keydown", e => { if (e.key === "Escape") { ov.remove(); resolve(buttons[buttons.length - 1]); } });
            document.body.appendChild(ov);
        });
    };

    window.postJSON = async function (url, data) {
        const r = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
            body: JSON.stringify(data),
        });
        if (r.status === 401 || r.redirected) { window.top.location.reload(); throw new Error("signed out"); }
        let body = {};
        try { body = await r.json(); } catch (e) { body = { error: "The server could not complete the request." }; }
        if (!r.ok) throw new Error(body.error || "The server could not complete the request.");
        return body;
    };

    /* Close this screen's popup window (Access DoCmd.Close) */
    window.closeForm = function () {
        if (window.parent !== window && window.parent.SCSWindows) window.parent.SCSWindows.close(window);
        else window.close();
    };
})();

/* ── Date fields (Access: date picker icon + short dates such as "15-10" take the current year) ── */
(function () {
    const MON = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"];
    const pad = n => String(n).padStart(2, "0");
    const show = d => pad(d.getDate()) + "-" + pad(d.getMonth() + 1) + "-" + d.getFullYear();

    function mk(d, m, y) {
        const dt = new Date(y, m - 1, d);
        return dt.getFullYear() === y && dt.getMonth() === m - 1 && dt.getDate() === d ? dt : null;
    }
    function parse(s) {
        s = (s || "").trim().toLowerCase();
        if (!s) return null;
        const iso = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
        if (iso) return mk(+iso[3], +iso[2], +iso[1]);
        const p = s.split(/[\s\-\/.,]+/).filter(Boolean);
        if (p.length < 2 || p.length > 3) return null;
        const num = x => /^\d+$/.test(x);
        let d, mo;
        if (num(p[0]) && num(p[1])) { d = +p[0]; mo = +p[1]; }
        else if (num(p[0]) && MON.includes(p[1].slice(0, 3))) { d = +p[0]; mo = MON.indexOf(p[1].slice(0, 3)) + 1; }
        else if (MON.includes(p[0].slice(0, 3)) && num(p[1])) { d = +p[1]; mo = MON.indexOf(p[0].slice(0, 3)) + 1; }
        else return null;
        let y = new Date().getFullYear();
        if (p.length === 3) { if (!num(p[2])) return null; y = +p[2] + (p[2].length <= 2 ? 2000 : 0); }
        return mk(d, mo, y);
    }
    window.parseAccessDate = parse;

    // Complete short dates before the screen saves them (capture phase runs before the screen's own handlers)
    document.addEventListener("change", function (e) {
        const el = e.target;
        if (!el.matches || !el.matches("input[data-date]")) return;
        const d = parse(el.value);
        if (d) el.value = show(d);
    }, true);

    // Calendar button next to the focused date field, like the Access date picker
    let btn = null, cal = null, target = null;
    function hideCal() { if (cal) { cal.remove(); cal = null; } }
    document.addEventListener("focusin", function (e) {
        const el = e.target;
        if (el.closest && el.closest(".acc-cal, .acc-cal-btn")) return;
        if (!el.matches || !el.matches("input[data-date]") || el.readOnly) {
            if (btn) { btn.remove(); btn = null; }
            hideCal();
            return;
        }
        target = el;
        if (!btn) {
            btn = document.createElement("button");
            btn.type = "button";
            btn.className = "acc-cal-btn";
            btn.title = "Choose a date";
            btn.tabIndex = -1;
            btn.innerHTML = "&#128197;";
            btn.addEventListener("mousedown", function (ev) { ev.preventDefault(); });
            btn.addEventListener("click", function () { openCal(target); });
        }
        el.parentNode.appendChild(btn);
        btn.style.left = (el.offsetLeft + el.offsetWidth + 2) + "px";
        btn.style.top = el.offsetTop + "px";
        btn.style.height = el.offsetHeight + "px";
    });

    function openCal(el) {
        hideCal();
        const cur = parse(el.value);
        const base = cur || new Date();
        let y = base.getFullYear(), m = base.getMonth();
        cal = document.createElement("div");
        cal.className = "acc-cal";
        cal.addEventListener("mousedown", function (ev) { ev.preventDefault(); });
        const r = el.getBoundingClientRect();
        cal.style.left = Math.max(0, Math.min(r.left, window.innerWidth - 226)) + "px";
        cal.style.top = (r.bottom + 194 > window.innerHeight ? Math.max(0, r.top - 194) : r.bottom + 2) + "px";
        document.body.appendChild(cal);
        function draw() {
            const first = new Date(y, m, 1), start = (first.getDay() + 6) % 7, days = new Date(y, m + 1, 0).getDate();
            const today = new Date();
            let h = '<div class="cal-head"><button data-n="-1">&#9664;</button><span>' +
                first.toLocaleString("en", { month: "long" }) + " " + y + '</span><button data-n="1">&#9654;</button></div><div class="cal-grid">';
            ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"].forEach(function (d) { h += "<b>" + d + "</b>"; });
            for (let i = 0; i < start; i++) h += "<i></i>";
            for (let d = 1; d <= days; d++) {
                const sel = cur && cur.getFullYear() === y && cur.getMonth() === m && cur.getDate() === d;
                const tod = today.getFullYear() === y && today.getMonth() === m && today.getDate() === d;
                h += '<a data-d="' + d + '" class="' + (sel ? "sel " : "") + (tod ? "today" : "") + '">' + d + "</a>";
            }
            h += '</div><div class="cal-foot"><a data-today="1">Today</a></div>';
            cal.innerHTML = h;
        }
        cal.addEventListener("click", function (ev) {
            const t = ev.target;
            if (t.dataset.n) { m += +t.dataset.n; if (m < 0) { m = 11; y--; } if (m > 11) { m = 0; y++; } draw(); return; }
            let picked = null;
            if (t.dataset.d) picked = new Date(y, m, +t.dataset.d);
            if (t.dataset.today) picked = new Date();
            if (!picked) return;
            el.value = show(picked);
            el.dispatchEvent(new Event("input", { bubbles: true }));
            el.dispatchEvent(new Event("change", { bubbles: true }));
            hideCal();
            el.focus();
        });
        draw();
    }
    document.addEventListener("mousedown", function (e) { if (cal && !e.target.closest(".acc-cal, .acc-cal-btn")) hideCal(); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") hideCal(); });
})();
