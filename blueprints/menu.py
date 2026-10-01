"""Main Menu — a replica of the Access form `MainMenu` (spec 0, section A)."""
from flask import Blueprint, render_template, request, url_for
from flask_login import login_required

bp = Blueprint("menu", __name__)

# Group boxes: caption, frame x/y/w/h, caption tab x/w (Access positions in px)
FRAMES = [
    ("Purchase Orders", 336, 20, 348, 244, 461, 120),
    ("Stock, Delivery, and Invoices", 708, 20, 348, 244, 794, 197),
    ("Shipment Files", 340, 288, 348, 180, 472, 106),
    ("Customers PO's", 708, 288, 348, 180, 836, 113),
    ("Commission, Service, and Detention Invoices", 340, 488, 348, 208, 364, 303),
    ("Master Data", 708, 488, 348, 208, 731, 305),
]

# Icon buttons (style A): x, y, icon, text, screen key (services.screens REGISTRY), Access object, phase,
# parameter prompt (Access "Enter Parameter Value" asked before the screen opens)
ITEMS = [
    # Purchase Orders
    (356, 48, "1cbd854c_notebook", "Create new MPC PO", "new_po", "New PO", 2, None),
    (356, 84, "7441a42d_clock", "Updation of ETD, ETA, and Pay req.", "updation_eta", "Updation of ETD, ETA and Pay requests", 2, None),
    (356, 120, "c7054ca8_notebook_alt", "Incoming Shipments Report", "rpt_incoming", "Incoming Shipments Report", 2, None),
    (356, 156, "1cbd854c_notebook", "Pending Payments Report", "rpt_payments", "Payments Required", 2, None),
    (356, 192, "1cbd854c_notebook", "Cleared Shipments Report", "rpt_cleared", "ClearedShipmentsReport", 2, None),
    (356, 228, "d2ddad11_clipboard_folder", "Add Import Permit", "add_permit", "AddPermit", 2, None),
    # Stock, Delivery, and Invoices
    (728, 48, "1cbd854c_notebook", "Updation of Clearance Status (GR)", "update_clearance_gr", "UpdateClearanceGR", 4, "Enter S/F number:"),
    (728, 84, "cae16295_edit_doc", "Local Stock of Single Product", "local_stock_rpt", "LocalStockRpt", 4, None),
    (728, 120, "ac6ddeb0_copy_docs", "Create/Amend Delivery Note", "dn_particular", "DNParticular", 4, None),
    (728, 156, "d144235c_plus_bang", "Deliver multi-items", "multi_dn_no", "MultiDNNo", 4, None),
    (728, 192, "c7054ca8_notebook_alt", "Shipments Delivered without Invoice", "rpt_dlvrd_wo_inv", "ShipmentsDlvrdWOInv", 4, None),
    (728, 228, "dd67f8a8_form_stack_alt", "Updation of Delivery/Invoice", "updation_of_inv", "UpdationOfInv", 4, "Enter the SF no:"),
    # Shipment Files
    (356, 320, "1cbd854c_notebook", "Create new S/F", "sf", "SF", 3, None),
    (356, 356, "d144235c_plus_bang", "Add S/F Items", "copy_sf", "Copy SF", 3, "Enter S/F number"),
    (356, 392, "4d2a44da_envelope", "Docs to Broker", "sf_broker_cover", "SF_BrokerCover", 3, None),
    (356, 428, "5a417896_grid", "Full S/F Details", "sf_full_details_locked", "SFFullDetails_Locked", 3, None),
    # Customers PO's
    (728, 316, "1cbd854c_notebook", "Add new Customer PO", "add_new_cus_po", "AddNewCusPO", 5, None),
    (728, 352, "d144235c_plus_bang", "Customers PO Report", "cus_po_rpt", "CusPORpt", 5, None),
    (728, 388, "d2738f13_folder_star", "Inquiry of Single PO", "rpt_single_po", "DeliveryReportofSinglePO", 5, "Enter the PO#"),
    (728, 424, "23f7303b_calendar_color", "Delivery Schedule", "delivery_schedule", "DeliverySchedule", 5, None),
    # Commission, Service, and Detention Invoices
    (356, 516, "213ac306_notebooks_stack", "FCC Commission Invoices (Pending)", "fcc_commission_inv", "FCCCommissionInv", 6, None),
    (356, 552, "c7054ca8_notebook_alt", "FCC Commission Invoices Report (All)", "rpt_fcc_commission", "FCCCommissionReport", 6, None),
    (356, 588, "213ac306_notebooks_stack", "FCC Handling Invoices (Pending)", "fcc_service_inv", "FCCServiceInv", 6, None),
    (356, 624, "213ac306_notebooks_stack", "n-Heptane ISO-Tank Rental Invoices", "tank_rental_charges", "TankRentalCharges", 6, None),
    (356, 660, "bba600ce_notebooks_stack_alt", "Tanks Not-Returned to SL Report", "rpt_tanks_not_returned", "TanksNotReturnedReport", 6, None),
]

# Master Data buttons (style B): x, y, width, caption, master form key
MASTER_BUTTONS = [
    (720, 524, 100, " Customers", "customers"),
    (828, 524, 100, " Products", "products"),
    (936, 524, 112, " Customers Add", "customer_address"),
    (720, 561, 100, " Brokers", "brokers"),
    (828, 561, 100, " Packing", "packing"),
    (936, 561, 112, " Shipping Lines", "shipping_lines"),
    (720, 598, 100, " Trans.", "transporters"),
    (828, 598, 100, " Suppliers", "suppliers"),
    (936, 598, 112, " SL Terminals", "returning_terminal"),
]


@bp.route("/menu")
@login_required
def main_menu():
    from blueprints.master import FORMS, window_size

    from services.screens import REGISTRY, window_size as screen_size
    items = []
    for x, y, icon, text, key, obj, phase, prompt in ITEMS:
        d = REGISTRY.get(key)
        if d:
            w, h = screen_size(d) if d["kind"] != "report" else (1180, 820)
            url = {"form": "/f/", "grid": "/g/", "report": "/r/"}[d["kind"]] + key
            title = d.get("title", obj)
        else:
            w, h, url, title = 440, 190, url_for("menu.not_ready", name=obj, phase=phase), obj
            prompt = None
        items.append(dict(x=x, y=y, icon=icon, text=text, url=url, title=title, w=w, h=h, prompt=prompt))
    masters = []
    for x, y, w, caption, key in MASTER_BUTTONS:
        ww, wh = window_size(FORMS[key])
        masters.append(dict(x=x, y=y, w=w, caption=caption, url=url_for("master.form", key=key),
                            title=FORMS[key]["title"], ww=ww, wh=wh))
    return render_template("access/main_menu.html", frames=FRAMES, items=items, masters=masters)


@bp.route("/not-ready")
@login_required
def not_ready():
    return render_template("access/not_ready.html", name=request.args.get("name", ""),
                           phase=request.args.get("phase", ""))
