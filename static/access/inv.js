/* Commission, Service and Detention invoice grids. */

/* Access "Show Invoice(s) Description": rows grow and the hidden description, its label and the
   update button become visible on every row (until the window closes). */
function invShowDesc(api, a) {
    if (document.body.classList.contains("show-desc")) return;
    const st = document.createElement("style");
    st.textContent = `.show-desc .grow { height: ${a.h}px !important; }
        .show-desc .grow textarea { display: block !important; }
        .show-desc .grow .lbl, .show-desc .grow .abtn { display: flex !important; }`;
    document.head.appendChild(st);
    document.body.classList.add("show-desc");
}

/* Footer "Total Estimated Commission Value" = sum of the rows' estimated commission. */
window.addEventListener("load", () => {
    const tot = document.getElementById("f_TotalCom");
    if (!tot || !window.grid) return;
    const sum = window.grid.rows.reduce((s, r) => s + (parseFloat(String(r.EstCom || "0").replace(/,/g, "")) || 0), 0);
    tot.value = sum.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
});
