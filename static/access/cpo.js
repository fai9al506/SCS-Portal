/* Customers PO's: filter dialogs (Access forms CusPORpt and DeliverySchedule). */
function _openReport(url, title) {
    const open = window.parent !== window && window.parent.SCSWindows ? window.parent.SCSWindows.open : (u) => window.open(u, "_blank");
    open(url, title, 1180, 820);
}

/* CusPORpt "Open Report": product required; Active only -> CusPOBalanceActive, else CusPOBalance.
   Unlike Access, the dialog stays open after the warning (decision: bug 11). */
async function cusPoRptOpen() {
    const product = document.getElementById("f_Product").value.trim();
    const customer = document.getElementById("f_Customer").value.trim();
    if (!product) { await msgBox("You have to enter product!"); document.getElementById("f_Product").focus(); return; }
    const active = document.getElementById("f_ActiveOnly").checked;
    const q = new URLSearchParams({ product, customer }).toString();
    _openReport(`/r/${active ? "rpt_cus_po_balance_active" : "rpt_cus_po_balance"}?${q}`,
                active ? "CusPOBalanceActive" : "CusPOBalance");
    closeForm();
}

/* DeliverySchedule "Open Report": product optional (blank = all products). */
function deliveryScheduleOpen() {
    const product = document.getElementById("f_Product").value.trim();
    _openReport(`/r/rpt_delivery_schedule?${new URLSearchParams({ product })}`, "Delivery Schedule");
    closeForm();
}
