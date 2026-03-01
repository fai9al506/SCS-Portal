from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from extensions import db


def utcnow():
    return datetime.now(timezone.utc)


# ── User ────────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    role = db.Column(db.String(20), nullable=False, default="Logistics")
    # Roles: Admin / Manager / Logistics / Buyer
    password_hash = db.Column(db.String(256), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# ── Lookup Tables ───────────────────────────────────────────────────

class ProductCategory(db.Model):
    __tablename__ = "product_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)


class Currency(db.Model):
    __tablename__ = "currencies"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False)
    name = db.Column(db.String(50), nullable=True)
    is_active = db.Column(db.Boolean, default=True)


class ShippingLine(db.Model):
    __tablename__ = "shipping_lines"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    legacy_id = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Boolean, default=True)


class PortOfDestination(db.Model):
    __tablename__ = "ports_of_destination"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    legacy_id = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Boolean, default=True)


class ReturnTerminal(db.Model):
    __tablename__ = "return_terminals"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    legacy_id = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Boolean, default=True)


# ── Master Data ─────────────────────────────────────────────────────

class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    sap_code = db.Column(db.String(50), nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey("product_categories.id"), nullable=True)
    legacy_id = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    category = db.relationship("ProductCategory")


class Supplier(db.Model):
    __tablename__ = "suppliers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    sap_no = db.Column(db.String(50), nullable=True)
    address = db.Column(db.Text, nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    contact_person = db.Column(db.String(200), nullable=True)
    legacy_id = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)


class Customer(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    sap_id = db.Column(db.String(50), nullable=True)
    legacy_id = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    addresses = db.relationship("CustomerAddress", back_populates="customer", cascade="all, delete-orphan")


class CustomerAddress(db.Model):
    __tablename__ = "customer_addresses"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    plant = db.Column(db.String(200), nullable=True)
    address_line1 = db.Column(db.String(300), nullable=True)
    address_line2 = db.Column(db.String(300), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    contact_person = db.Column(db.String(200), nullable=True)
    contact_phone = db.Column(db.String(50), nullable=True)
    contact_email = db.Column(db.String(255), nullable=True)
    legacy_id = db.Column(db.Integer, nullable=True)

    customer = db.relationship("Customer", back_populates="addresses")


class Broker(db.Model):
    __tablename__ = "brokers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(300), nullable=True)
    address = db.Column(db.Text, nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    legacy_id = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)


class Transporter(db.Model):
    __tablename__ = "transporters"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    legacy_id = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)


class StorageLocation(db.Model):
    __tablename__ = "storage_locations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(255), nullable=True)
    legacy_id = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)


# ── Permits ─────────────────────────────────────────────────────────

class Permit(db.Model):
    __tablename__ = "permits"

    id = db.Column(db.Integer, primary_key=True)
    permit_no = db.Column(db.String(50), nullable=True)
    product_name = db.Column(db.String(200), nullable=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    hs_code = db.Column(db.String(20), nullable=True)
    expiry_date = db.Column(db.Date, nullable=True)
    duty_percent = db.Column(db.Float, nullable=True)
    qty = db.Column(db.Float, nullable=True)
    qty_used = db.Column(db.Float, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    legacy_id = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    product = db.relationship("Product")


# ── Shipment File (Core) ────────────────────────────────────────────

class ShipmentFile(db.Model):
    __tablename__ = "shipment_files"

    id = db.Column(db.Integer, primary_key=True)
    sf_number = db.Column(db.String(20), nullable=True, index=True)
    legacy_id = db.Column(db.Integer, nullable=True)
    entry_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(30), default="Open")
    # Status: Open / In Transit / At Port / Clearing / Cleared / Delivered / Closed / Cancelled

    # ── PO & Supplier Details ───────────────────────────────────────
    po_ref = db.Column(db.String(50), nullable=True)
    po_item_no = db.Column(db.String(10), nullable=True)  # PO line item number
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True)
    supplier_name = db.Column(db.String(200), nullable=True)  # Denormalized for legacy
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    product_name = db.Column(db.String(200), nullable=True)  # Denormalized for legacy
    qty = db.Column(db.Float, nullable=True)
    uom = db.Column(db.String(30), nullable=True)
    packing = db.Column(db.String(100), nullable=True)
    unit_price = db.Column(db.Float, nullable=True)
    currency = db.Column(db.String(10), nullable=True)
    total_value = db.Column(db.Float, nullable=True)
    payment_terms = db.Column(db.String(100), nullable=True)
    incoterm = db.Column(db.String(20), nullable=True)
    origin_country = db.Column(db.String(100), nullable=True)

    # ── Shipping Details ────────────────────────────────────────────
    container_no = db.Column(db.String(50), nullable=True)
    container_size = db.Column(db.String(20), nullable=True)
    seal_no = db.Column(db.String(50), nullable=True)
    shipping_line_id = db.Column(db.Integer, db.ForeignKey("shipping_lines.id"), nullable=True)
    shipping_line_name = db.Column(db.String(200), nullable=True)
    vessel_name = db.Column(db.String(200), nullable=True)
    voyage_no = db.Column(db.String(50), nullable=True)
    bol_no = db.Column(db.String(50), nullable=True)
    bol_date = db.Column(db.Date, nullable=True)
    port_of_loading = db.Column(db.String(100), nullable=True)
    port_of_destination_id = db.Column(db.Integer, db.ForeignKey("ports_of_destination.id"), nullable=True)
    port_of_destination_name = db.Column(db.String(100), nullable=True)
    etd = db.Column(db.Date, nullable=True)
    eta = db.Column(db.Date, nullable=True)
    actual_arrival = db.Column(db.Date, nullable=True)
    free_time_days = db.Column(db.Integer, nullable=True)
    free_time_expiry = db.Column(db.Date, nullable=True)

    # ── Clearance Details ───────────────────────────────────────────
    broker_id = db.Column(db.Integer, db.ForeignKey("brokers.id"), nullable=True)
    broker_name = db.Column(db.String(200), nullable=True)
    permit_id = db.Column(db.Integer, db.ForeignKey("permits.id"), nullable=True)
    permit_no = db.Column(db.String(50), nullable=True)
    docs_to_broker_date = db.Column(db.Date, nullable=True)
    bayan_no = db.Column(db.String(50), nullable=True)
    bayan_date = db.Column(db.Date, nullable=True)
    clearance_date = db.Column(db.Date, nullable=True)
    clearance_status = db.Column(db.String(30), nullable=True)
    duty_amount = db.Column(db.Float, nullable=True)
    vat_amount = db.Column(db.Float, nullable=True)
    customs_other_charges = db.Column(db.Float, nullable=True)

    # ── Stock & Delivery ────────────────────────────────────────────
    storage_location_id = db.Column(db.Integer, db.ForeignKey("storage_locations.id"), nullable=True)
    storage_location_name = db.Column(db.String(200), nullable=True)
    grn_no = db.Column(db.String(50), nullable=True)
    gr_date = db.Column(db.Date, nullable=True)
    gr_qty = db.Column(db.Float, nullable=True)
    delivery_customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True)
    delivery_customer_name = db.Column(db.String(200), nullable=True)
    delivery_plant = db.Column(db.String(200), nullable=True)
    delivery_address = db.Column(db.Text, nullable=True)
    delivery_contact = db.Column(db.String(200), nullable=True)
    transporter_id = db.Column(db.Integer, db.ForeignKey("transporters.id"), nullable=True)
    transporter_name = db.Column(db.String(200), nullable=True)
    dn_no = db.Column(db.String(50), nullable=True)
    dn_date = db.Column(db.Date, nullable=True)
    delivery_date = db.Column(db.Date, nullable=True)
    pod_received = db.Column(db.Boolean, default=False)  # Proof of delivery

    # ── Container Return ────────────────────────────────────────────
    arrival_to_port_date = db.Column(db.Date, nullable=True)
    empty_pickup_date = db.Column(db.Date, nullable=True)
    return_terminal_id = db.Column(db.Integer, db.ForeignKey("return_terminals.id"), nullable=True)
    return_terminal_name = db.Column(db.String(200), nullable=True)
    eir_no = db.Column(db.String(50), nullable=True)
    container_return_date = db.Column(db.Date, nullable=True)
    container_return_done = db.Column(db.Boolean, default=False)

    # ── Invoicing ───────────────────────────────────────────────────
    supplier_invoice_no = db.Column(db.String(50), nullable=True)
    supplier_invoice_date = db.Column(db.Date, nullable=True)
    supplier_invoice_amount = db.Column(db.Float, nullable=True)
    customer_invoice_no = db.Column(db.String(50), nullable=True)
    customer_invoice_date = db.Column(db.Date, nullable=True)
    customer_invoice_amount = db.Column(db.Float, nullable=True)
    detention_invoice = db.Column(db.String(50), nullable=True)
    detention_amount = db.Column(db.Float, nullable=True)
    commission_invoice = db.Column(db.String(50), nullable=True)
    commission_amount = db.Column(db.Float, nullable=True)
    service_invoice = db.Column(db.String(50), nullable=True)
    service_amount = db.Column(db.Float, nullable=True)
    freight_invoice = db.Column(db.String(50), nullable=True)
    freight_amount = db.Column(db.Float, nullable=True)
    invoices_submitted = db.Column(db.Boolean, default=False)

    # ── Notes ───────────────────────────────────────────────────────
    notes = db.Column(db.Text, nullable=True)

    # ── Timestamps ──────────────────────────────────────────────────
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # ── Relationships ───────────────────────────────────────────────
    supplier = db.relationship("Supplier", foreign_keys=[supplier_id])
    product = db.relationship("Product", foreign_keys=[product_id])
    shipping_line = db.relationship("ShippingLine", foreign_keys=[shipping_line_id])
    port_of_destination = db.relationship("PortOfDestination", foreign_keys=[port_of_destination_id])
    broker = db.relationship("Broker", foreign_keys=[broker_id])
    permit = db.relationship("Permit", foreign_keys=[permit_id])
    storage_location = db.relationship("StorageLocation", foreign_keys=[storage_location_id])
    delivery_customer = db.relationship("Customer", foreign_keys=[delivery_customer_id])
    transporter = db.relationship("Transporter", foreign_keys=[transporter_id])
    return_terminal = db.relationship("ReturnTerminal", foreign_keys=[return_terminal_id])
    creator = db.relationship("User", foreign_keys=[created_by])

    payment_tracking = db.relationship("ShipmentPaymentTracking", back_populates="shipment", uselist=False)
    broker_covers = db.relationship("BrokerCover", back_populates="shipment")


# ── Customer PO ─────────────────────────────────────────────────────

class CustomerPO(db.Model):
    __tablename__ = "customer_pos"

    id = db.Column(db.Integer, primary_key=True)
    po_no = db.Column(db.String(50), nullable=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True)
    customer_name = db.Column(db.String(200), nullable=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    product_name = db.Column(db.String(200), nullable=True)
    qty = db.Column(db.Float, nullable=True)
    uom = db.Column(db.String(30), nullable=True)
    unit_price = db.Column(db.Float, nullable=True)
    currency = db.Column(db.String(10), nullable=True)
    total_value = db.Column(db.Float, nullable=True)
    payment_terms = db.Column(db.String(100), nullable=True)
    incoterm = db.Column(db.String(20), nullable=True)
    delivery_location = db.Column(db.String(200), nullable=True)
    po_date = db.Column(db.Date, nullable=True)
    delivery_date = db.Column(db.Date, nullable=True)
    is_closed = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text, nullable=True)
    legacy_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    customer = db.relationship("Customer", foreign_keys=[customer_id])
    product = db.relationship("Product", foreign_keys=[product_id])


# ── Shipment Payment Tracking ───────────────────────────────────────

class ShipmentPaymentTracking(db.Model):
    __tablename__ = "shipment_payment_tracking"

    id = db.Column(db.Integer, primary_key=True)
    shipment_id = db.Column(db.Integer, db.ForeignKey("shipment_files.id"), nullable=False)

    # Payment stages
    advance_payment_date = db.Column(db.Date, nullable=True)
    advance_payment_amount = db.Column(db.Float, nullable=True)
    advance_payment_ref = db.Column(db.String(50), nullable=True)

    balance_payment_date = db.Column(db.Date, nullable=True)
    balance_payment_amount = db.Column(db.Float, nullable=True)
    balance_payment_ref = db.Column(db.String(50), nullable=True)

    lc_no = db.Column(db.String(50), nullable=True)
    lc_date = db.Column(db.Date, nullable=True)
    lc_amount = db.Column(db.Float, nullable=True)
    lc_expiry = db.Column(db.Date, nullable=True)

    # Clearance cost tracking
    duty_paid = db.Column(db.Boolean, default=False)
    duty_payment_date = db.Column(db.Date, nullable=True)
    vat_paid = db.Column(db.Boolean, default=False)
    vat_payment_date = db.Column(db.Date, nullable=True)

    payment_status = db.Column(db.String(30), nullable=True)
    # Pending / Partial / Paid / Overdue
    notes = db.Column(db.Text, nullable=True)
    legacy_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    shipment = db.relationship("ShipmentFile", back_populates="payment_tracking")


# ── Broker Cover ────────────────────────────────────────────────────

class BrokerCover(db.Model):
    __tablename__ = "broker_covers"

    id = db.Column(db.Integer, primary_key=True)
    shipment_id = db.Column(db.Integer, db.ForeignKey("shipment_files.id"), nullable=False)
    cover_date = db.Column(db.Date, nullable=True)
    doc_count = db.Column(db.Integer, nullable=True)
    bol_copies = db.Column(db.Integer, nullable=True)
    invoice_copies = db.Column(db.Integer, nullable=True)
    packing_list_copies = db.Column(db.Integer, nullable=True)
    coa_copies = db.Column(db.Integer, nullable=True)
    other_docs = db.Column(db.Text, nullable=True)
    courier_name = db.Column(db.String(100), nullable=True)
    courier_tracking = db.Column(db.String(100), nullable=True)
    courier_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    legacy_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    shipment = db.relationship("ShipmentFile", back_populates="broker_covers")


# ── Customer Contract (Schema Only) ────────────────────────────────

class CustomerContract(db.Model):
    __tablename__ = "customer_contracts"

    id = db.Column(db.Integer, primary_key=True)
    contract_no = db.Column(db.String(50), nullable=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True)
    customer_name = db.Column(db.String(200), nullable=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    product_name = db.Column(db.String(200), nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    unit_price = db.Column(db.Float, nullable=True)
    currency = db.Column(db.String(10), nullable=True)
    qty = db.Column(db.Float, nullable=True)
    uom = db.Column(db.String(30), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    customer = db.relationship("Customer", foreign_keys=[customer_id])
    product = db.relationship("Product", foreign_keys=[product_id])


# ── Audit Log ───────────────────────────────────────────────────────

class AuditLog(db.Model):
    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, nullable=True)
    actor_type = db.Column(db.String(20), nullable=False, default="User")
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(db.Integer, nullable=True)
    before_json = db.Column(db.JSON, nullable=True)
    after_json = db.Column(db.JSON, nullable=True)
    timestamp = db.Column(db.DateTime, default=utcnow)
