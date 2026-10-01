/* Stock, Delivery, and Invoices section: Delivery Note buttons, e-mails, MultiDN, DN-number prompt. */

/* Open another screen in a popup window, sized from the server's screen definition. */
async function stockOpen(key, url, title) {
    let w = 1180, h = 820;
    try {
        const s = await (await fetch(`/screen-size/${key}`)).json();
        if (!url.startsWith("/r/")) { w = s.w; h = s.h; }
        title = title || s.title;
    } catch (e) { /* default size */ }
    const open = window.parent !== window && window.parent.SCSWindows ? window.parent.SCSWindows.open : (u) => window.open(u, "_blank");
    return open(url, title || "", w, h);
}

/* Download a PDF / Outlook draft; a server message is shown as an Access message box instead. */
async function stockDownload(url) {
    const r = await fetch(url);
    if (!r.ok) { await msgBox(await r.text()); return; }
    const blob = await r.blob();
    const cd = r.headers.get("Content-Disposition") || "";
    const m = cd.match(/filename="([^"]+)"/);
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = m ? m[1] : "download";
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
}

const checked = id => { const e = document.getElementById(id); return e && e.checked ? "1" : "0"; };

/* LocalStockRpt "Open Report": open the stock report of the chosen product and close the dialog. */
async function openLocalStock(form) {
    const product = document.getElementById("f_Combo4").value.trim();
    await stockOpen("rpt_local_stock", "/r/rpt_local_stock?product=" + encodeURIComponent(product), "Local Stock of Product");
    closeForm();
}

/* DN / DNParticular */
async function dnReady(form) {
    if (!(await form.commit())) return null;
    const r = form.current();
    if (!r._id) { await msgBox("An error was occurred, please check if there is info missing."); return null; }
    if (!String(r.DeliveredPOItem ?? "").trim()) await msgBox("PO Item number is missing, please check!", { icon: "warn" });
    return r;
}
async function dnPrint(form, a) {
    const r = await dnReady(form);
    if (r) await stockDownload(`/pdf/${a.pdf}?id=${r._id}`);
}
async function dnEmail(form, a) {
    const r = await dnReady(form);
    if (r) await stockDownload(`/e/${a.kind}?id=${r._id}&gp=${checked("f_CheckGP")}`);
}

/* MultiDNNo "Create Delivery Note(s)" */
async function openMultiDN(form) {
    const dns = [];
    for (let i = 1; i <= 10; i++) {
        const v = (document.getElementById("f_DN" + i).value || "").trim();
        if (v) dns.push(v);
    }
    await stockOpen("multi_dn", "/g/multi_dn?dns=" + encodeURIComponent(dns.join(",")), "Create Delivery Note");
}

/* MultiDN footer buttons (act on all listed rows; single values come from the current row, as in Access) */
async function multiReady(g) {
    if (!(await g.commitRow(g.cur))) return null;
    if (!g.rows.length) { await msgBox("An error was occurred, please check if there is info missing."); return null; }
    if (g.rows.some(r => !String(r.DeliveredPOItem ?? "").trim())) await msgBox("PO Item number is missing, please check!", { icon: "warn" });
    const cur = (g.rows[g.cur] || g.rows[g.rows.length - 1])._id;
    return { dns: g.rows.map(r => r._id).join(","), cur };
}
async function multiPrint(g) {
    const s = await multiReady(g);
    if (s) await stockDownload(`/pdf/multi_dn_pdf?dns=${s.dns}`);
}
async function multiEmail(g, a) {
    const s = await multiReady(g);
    if (!s) return;
    const mso = (document.getElementById("f_MSOn") || {}).value || "";
    await stockDownload(`/e/${a.kind}?dns=${s.dns}&cur=${s.cur}&mp=${checked("f_CheckMP")}&gp=${checked("f_CheckGP")}&mso=${encodeURIComponent(mso)}`);
}

document.addEventListener("DOMContentLoaded", () => {
    const path = location.pathname;
    const params = new URLSearchParams(location.search);

    // DNParticular: Access asked "Enter the DN number:" before opening the form
    if (path === "/f/dn_particular" && !params.get("p")) {
        const ov = document.createElement("div");
        ov.className = "msg-overlay";
        ov.innerHTML = '<div class="msg-box param-box" style="width:300px"><div class="msg-title">Enter Parameter Value</div>' +
            '<div class="msg-body"><span>Enter the DN number:</span><input type="text"></div>' +
            '<div class="msg-actions"><button class="ok">OK</button><button class="cancel">Cancel</button></div></div>';
        const inp = ov.querySelector("input");
        const ok = () => { location.replace(path + "?p=" + encodeURIComponent(inp.value.trim())); };
        ov.querySelector(".ok").onclick = ok;
        ov.querySelector(".cancel").onclick = () => closeForm();
        ov.addEventListener("keydown", e => { if (e.key === "Enter") ok(); if (e.key === "Escape") closeForm(); });
        document.body.appendChild(ov);
        setTimeout(() => inp.focus(), 50);
    }

    // MultiDN footer: total quantity of the listed rows; "Multi products" shows the manual SO box
    if (path === "/g/multi_dn" && window.grid) {
        const sum = window.grid.rows.reduce((s, r) => s + (parseFloat(String(r.SFQty || "0").replace(/,/g, "")) || 0), 0);
        const box = document.getElementById("f_SumQty");
        if (box) box.value = sum.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        const mp = document.getElementById("f_CheckMP");
        if (mp) mp.addEventListener("change", () => {
            if (!mp.checked) return;             // Access left them visible once shown
            document.getElementById("f_MSOn").style.display = "";
            document.querySelectorAll(".sec .lbl").forEach(l => { if (l.textContent.includes("Please enter the SOs")) l.style.display = "flex"; });
        });
    }
});
