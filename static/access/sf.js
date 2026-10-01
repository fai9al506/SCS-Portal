/* Shipment Files section: Docs-to-Broker option groups and actions, Copy SF (for LS) footer button. */

/* Access option group: unbound radio buttons, reset to "No" on every open. */
function sfRadio(name, x, y, value, checked) {
    const detail = document.querySelector(".sec.detail");
    const wrap = document.createElement("label");
    wrap.style.cssText = `position:absolute;left:${x}px;top:${y}px;display:flex;align-items:center;gap:4px;font:11pt Calibri,sans-serif;cursor:pointer`;
    wrap.innerHTML = `<input type="radio" name="${name}" value="${value}" ${checked ? "checked" : ""}><span>${value === 2 ? "Yes" : "No"}</span>`;
    detail.appendChild(wrap);
}

function sfOption(name) {
    const r = document.querySelector(`input[name="${name}"]:checked`);
    return r ? r.value : "1";
}

window.addEventListener("DOMContentLoaded", () => {
    if (!window.form || window.form.cfg.key !== "sf_broker_cover") return;
    sfRadio("ShowCusPO", 340, 240, 1, true);
    sfRadio("ShowCusPO", 396, 240, 2, false);
    sfRadio("SendDocsThruDHL", 340, 300, 1, true);
    sfRadio("SendDocsThruDHL", 396, 300, 2, false);
});

/* "Print the Cover Letter": save, then the cover letter with or without the customer PO. */
async function sfBrokerPrint(api) {
    if (!(await api.commit())) return;
    const id = api.rec._id;
    if (!id) { await msgBox("You must enter a value in the 'SF_BrokerCover.SFNo' field."); return; }
    const withPO = sfOption("ShowCusPO") === "2";
    api.openScreen({ url: `/r/rpt_broker_cover${withPO ? "_cuspo" : ""}?id=${id}`,
                     title: withPO ? "SF_BrokerCover_wCusPO" : "SF_BrokerCover", w: 900, h: 900 });
}

/* "Send Email": Outlook draft to the broker (CC Logistics); the user attaches the scans and sends. */
async function sfBrokerEmail(api) {
    if (!(await api.commit())) return;
    const id = api.rec._id;
    if (!id) { await msgBox("An error was occurred, please check if there is info missing."); return; }
    const url = `/e/broker_docs?id=${id}&cuspo=${sfOption("ShowCusPO")}&dhl=${sfOption("SendDocsThruDHL")}`;
    const r = await fetch(url);
    if (!r.ok) { await msgBox(await r.text()); return; }
    const blob = await r.blob();
    const name = (r.headers.get("Content-Disposition") || "").match(/filename="([^"]+)"/);
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name ? name[1] : "email.eml";
    document.body.appendChild(a); a.click(); a.remove();
}

/* Copy SF (for LS) footer: "Go back to the stock report" — open LocalStockRpt, close this list. */
async function sfBackToStock(api) {
    await api.commitRow(api.cur);
    let w = 440, h = 220, title = "LocalStockRpt";
    try {
        const s = await (await fetch("/screen-size/local_stock_rpt")).json();
        w = s.w; h = s.h; title = s.title;
    } catch (e) { /* stock screen not registered yet */ }
    if (window.parent !== window && window.parent.SCSWindows) window.parent.SCSWindows.open("/f/local_stock_rpt", title, w, h);
    closeForm();
}
