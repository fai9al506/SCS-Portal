/* Access-style popup windows over the Main Menu.
 * Every Access form is a non-modal PopUp: several can be open, each can be moved and closed,
 * and opening a form that is already open just brings it to the front.
 * Screens inside a window can call parent.SCSWindows.open(...) / .close(window).
 */
(function () {
    const ICON = document.documentElement.dataset.icon;
    const open = {};          // key -> window element
    let z = 10, cascade = 0;

    function activate(win) {
        document.querySelectorAll(".acc-window.popup").forEach(w => w.classList.add("inactive"));
        win.classList.remove("inactive");
        win.style.zIndex = ++z;
    }

    /* Close a window. Screens that hold unsaved edits save them first (Access saves on close). */
    async function close(win) {
        if (!win) return;
        const frame = win.querySelector("iframe");
        let before = null;
        try { before = frame.contentWindow.scsBeforeClose; } catch (e) { /* page not loaded */ }
        if (before && !(await before())) return;
        delete open[win.dataset.key];
        win.remove();
    }

    /* Access parameter prompt ("Enter Parameter Value"). Resolves the typed value, or null on Cancel. */
    function askParam(prompt) {
        return new Promise(resolve => {
            const ov = document.createElement("div");
            ov.className = "msg-overlay";
            ov.innerHTML = '<div class="msg-box param-box" style="width:300px"><div class="msg-title">Enter Parameter Value</div>' +
                '<div class="msg-body"><span class="p"></span><input type="text"></div>' +
                '<div class="msg-actions"><button class="ok">OK</button><button class="cancel">Cancel</button></div></div>';
            ov.querySelector(".p").textContent = prompt;
            const inp = ov.querySelector("input");
            const done = v => { ov.remove(); resolve(v); };
            ov.querySelector(".ok").onclick = () => done(inp.value);
            ov.querySelector(".cancel").onclick = () => done(null);
            ov.addEventListener("keydown", e => { if (e.key === "Enter") done(inp.value); if (e.key === "Escape") done(null); });
            document.body.appendChild(ov);
            inp.focus();
        });
    }

    async function openWindow(url, title, width, height, pos, prompt) {
        if (prompt) {
            const v = await askParam(prompt);
            if (v === null) return null;
            url += (url.includes("?") ? "&" : "?") + "p=" + encodeURIComponent(v.trim());
        }
        const key = url;
        if (open[key]) { activate(open[key]); return open[key]; }
        const ws = document.querySelector(".workspace");
        const win = document.createElement("div");
        win.className = "acc-window popup";
        win.dataset.key = key;
        win.style.width = width + "px";
        win.style.height = height + "px";
        let x, y;
        if (pos) { x = pos[0]; y = pos[1]; }
        else {
            x = Math.max(8, (ws.clientWidth - width) / 2 + cascade);
            y = Math.max(8, ws.scrollTop + (window.innerHeight - 32 - height) / 2 + cascade);
            cascade = (cascade + 24) % 120;
        }
        win.style.left = x + "px";
        win.style.top = y + "px";
        win.innerHTML =
            '<div class="acc-titlebar"><img src="' + ICON + '" alt=""><span class="t"></span>' +
            '<span class="x" title="Close">&#x2715;</span></div><iframe></iframe>';
        win.querySelector(".t").textContent = title;
        win.querySelector("iframe").src = url;
        win.querySelector(".x").onclick = () => close(win);
        win.addEventListener("mousedown", () => activate(win), true);
        dragBy(win.querySelector(".acc-titlebar"), win);
        ws.appendChild(win);
        open[key] = win;
        activate(win);
        return win;
    }

    function dragBy(handle, win) {
        handle.addEventListener("mousedown", e => {
            if (e.target.classList.contains("x")) return;
            const sx = e.clientX, sy = e.clientY, ox = win.offsetLeft, oy = win.offsetTop;
            const shield = document.createElement("div");      // keep mouse events off the iframes while dragging
            shield.style.cssText = "position:fixed;inset:0;z-index:99999;cursor:default";
            document.body.appendChild(shield);
            const move = ev => {
                win.style.left = Math.max(0, ox + ev.clientX - sx) + "px";
                win.style.top = Math.max(0, oy + ev.clientY - sy) + "px";
            };
            const up = () => { shield.remove(); document.removeEventListener("mousemove", move); document.removeEventListener("mouseup", up); };
            document.addEventListener("mousemove", move);
            document.addEventListener("mouseup", up);
            e.preventDefault();
        });
    }

    window.SCSWindows = {
        open: openWindow,
        close: frameWindow => {
            for (const k in open) {
                const f = open[k].querySelector("iframe");
                if (f && f.contentWindow === frameWindow) { close(open[k]); return; }
            }
        },
        setTitle: (frameWindow, title) => {
            for (const k in open) {
                const f = open[k].querySelector("iframe");
                if (f && f.contentWindow === frameWindow) open[k].querySelector(".t").textContent = title;
            }
        },
    };

    // Main Menu buttons and their text open the target screen
    document.addEventListener("click", e => {
        const el = e.target.closest("[data-open]");
        if (!el) return;
        const d = el.dataset;
        const pos = d.x ? [parseInt(d.x, 10), parseInt(d.y, 10)] : null;
        openWindow(d.open, d.title, parseInt(d.w, 10), parseInt(d.h, 10), pos, d.prompt);
    });
})();
