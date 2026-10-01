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
