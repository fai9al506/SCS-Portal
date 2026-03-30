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


class PackingType(db.Model):
    __tablename__ = "packing_types"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)


class PaymentTermSupplier(db.Model):
    __tablename__ = "payment_terms_supplier"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)


class PaymentTermCustomer(db.Model):
    __tablename__ = "payment_terms_customer"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)


class DeliveryTerm(db.Model):
    __tablename__ = "delivery_terms"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)


class PermitRequirement(db.Model):
    __tablename__ = "permit_requirements"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)


class UnitOfMeasure(db.Model):
    __tablename__ = "units_of_measure"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
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
    name_in_customs = db.Column(db.String(200), nullable=True)
    hs_code = db.Column(db.String(20), nullable=True)
    expiry_date = db.Column(db.Date, nullable=True)
    duty_percent = db.Column(db.Float, nullable=True)
    qty = db.Column(db.Float, nullable=True)
    qty_used = db.Column(db.Float, nullable=True)
    permit_requirement_id = db.Column(db.Integer, db.ForeignKey("permit_requirements.id"), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    legacy_id = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    product = db.relationship("Product")
    permit_requirement = db.relationship("PermitRequirement")


# ── Purchase Orders ─────────────────────────────────────────────────

class PurchaseOrder(db.Model):
    __tablename__ = "purchase_orders"

    id = db.Column(db.Integer, primary_key=True)
    po_number = db.Column(db.String(50), nullable=True, index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True)
    payment_terms_id = db.Column(db.Integer, db.ForeignKey("payment_terms_supplier.id"), nullable=True)
    status = db.Column(db.String(30), default="Ordered")
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    supplier = db.relationship("Supplier", foreign_keys=[supplier_id])
    payment_term = db.relationship("PaymentTermSupplier", foreign_keys=[payment_terms_id])
    creator = db.relationship("User", foreign_keys=[created_by])
    items = db.relationship("PurchaseOrderItem", back_populates="purchase_order", cascade="all, delete-orphan")


class PurchaseOrderItem(db.Model):
    __tablename__ = "purchase_order_items"

    id = db.Column(db.Integer, primary_key=True)
    po_id = db.Column(db.Integer, db.ForeignKey("purchase_orders.id"), nullable=False)
    item_no = db.Column(db.Integer, nullable=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    qty = db.Column(db.Float, nullable=True)
    uom = db.Column(db.String(30), nullable=True)
    unit_price = db.Column(db.Float, nullable=True)
    currency = db.Column(db.String(10), nullable=True)
    total_amount = db.Column(db.Float, nullable=True)
    etd = db.Column(db.Date, nullable=True)
    eta = db.Column(db.Date, nullable=True)
    lead_time = db.Column(db.Integer, nullable=True)
    port_of_destination_id = db.Column(db.Integer, db.ForeignKey("ports_of_destination.id"), nullable=True)
    permit_id = db.Column(db.Integer, db.ForeignKey("permits.id"), nullable=True)
    sap_code = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(30), default="Ordered")
    first_payment_status = db.Column(db.String(30), default="Pending")
    second_payment_status = db.Column(db.String(30), default="Pending")
    notes = db.Column(db.Text, nullable=True)

    purchase_order = db.relationship("PurchaseOrder", back_populates="items")
    product = db.relationship("Product", foreign_keys=[product_id])
    port_of_destination = db.relationship("PortOfDestination", foreign_keys=[port_of_destination_id])
    permit = db.relationship("Permit", foreign_keys=[permit_id])


# ── Shipment File (Header) ─────────────────────────────────────────

class ShipmentFile(db.Model):
    __tablename__ = "shipment_files"

    id = db.Column(db.Integer, primary_key=True)
    sf_number = db.Column(db.String(20), nullable=True, index=True)

    # ── PO Link ─────────────────────────────────────────────────────
    po_id = db.Column(db.Integer, db.ForeignKey("purchase_orders.id"), nullable=True)
    po_item_no = db.Column(db.Integer, nullable=True)

    # ── Supplier & Product ──────────────────────────────────────────
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True)
    supplier_name = db.Column(db.String(200), nullable=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    product_name = db.Column(db.String(200), nullable=True)

    # ── Shipping Details ────────────────────────────────────────────
    bol_no = db.Column(db.String(50), nullable=True)
    bol_date = db.Column(db.Date, nullable=True)
    shipping_line_id = db.Column(db.Integer, db.ForeignKey("shipping_lines.id"), nullable=True)
    etd = db.Column(db.Date, nullable=True)
    eta = db.Column(db.Date, nullable=True)
    actual_arrival = db.Column(db.Date, nullable=True)

    # ── Port ────────────────────────────────────────────────────────
    port_of_destination_id = db.Column(db.Integer, db.ForeignKey("ports_of_destination.id"), nullable=True)
    port_of_destination_name = db.Column(db.String(100), nullable=True)

    # ── Status ──────────────────────────────────────────────────────
    status = db.Column(db.String(30), default="Incoming")
    # Status: Incoming / Ordered / Cleared / Canceled

    # ── Customer & Broker ───────────────────────────────────────────
    intended_customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True)
    customer_po_id = db.Column(db.Integer, db.ForeignKey("customer_pos.id"), nullable=True)
    broker_id = db.Column(db.Integer, db.ForeignKey("brokers.id"), nullable=True)
    permit_id = db.Column(db.Integer, db.ForeignKey("permits.id"), nullable=True)

    # ── Supplier Invoice ────────────────────────────────────────────
    supplier_inv_no = db.Column(db.String(50), nullable=True)
    supplier_inv_date = db.Column(db.Date, nullable=True)
    unit_price = db.Column(db.Float, nullable=True)
    currency = db.Column(db.String(10), nullable=True)
    total_inv_amount = db.Column(db.Float, nullable=True)

    # ── Other Details ───────────────────────────────────────────────
    packing = db.Column(db.String(100), nullable=True)
    remarks = db.Column(db.Text, nullable=True)
    entry_date = db.Column(db.Date, nullable=True)
    legacy_id = db.Column(db.Integer, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    # ── Timestamps ──────────────────────────────────────────────────
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # ── Relationships ───────────────────────────────────────────────
    purchase_order = db.relationship("PurchaseOrder", foreign_keys=[po_id])
    supplier = db.relationship("Supplier", foreign_keys=[supplier_id])
    product = db.relationship("Product", foreign_keys=[product_id])
    shipping_line = db.relationship("ShippingLine", foreign_keys=[shipping_line_id])
    port_of_destination = db.relationship("PortOfDestination", foreign_keys=[port_of_destination_id])
    intended_customer = db.relationship("Customer", foreign_keys=[intended_customer_id])
    customer_po = db.relationship("CustomerPO", foreign_keys=[customer_po_id])
    broker = db.relationship("Broker", foreign_keys=[broker_id])
    permit = db.relationship("Permit", foreign_keys=[permit_id])
    creator = db.relationship("User", foreign_keys=[created_by])

    payment_tracking = db.relationship("ShipmentPaymentTracking", back_populates="shipment", uselist=False)
    broker_covers = db.relationship("BrokerCover", back_populates="shipment")
    containers = db.relationship("ShipmentContainer", back_populates="shipment", cascade="all, delete-orphan")


# ── Shipment Container ─────────────────────────────────────────────

class ShipmentContainer(db.Model):
    __tablename__ = "shipment_containers"

    id = db.Column(db.Integer, primary_key=True)
    shipment_id = db.Column(db.Integer, db.ForeignKey("shipment_files.id"), nullable=False)
    container_no = db.Column(db.String(50), nullable=True)
    qty = db.Column(db.Float, nullable=True)
    uom = db.Column(db.String(30), nullable=True)
    seal_no = db.Column(db.String(50), nullable=True)
    packing = db.Column(db.String(100), nullable=True)

    # ── Clearance ───────────────────────────────────────────────────
    clearance_status = db.Column(db.String(30), default="Incoming")
    clearance_date = db.Column(db.Date, nullable=True)

    # ── Storage & GR ────────────────────────────────────────────────
    storage_location_id = db.Column(db.Integer, db.ForeignKey("storage_locations.id"), nullable=True)
    storage_location_name = db.Column(db.String(200), nullable=True)
    gr_no = db.Column(db.String(50), nullable=True)
    gr_date = db.Column(db.Date, nullable=True)

    # ── Docs ────────────────────────────────────────────────────────
    supplier_inv_no = db.Column(db.String(50), nullable=True)
    bol_no = db.Column(db.String(50), nullable=True)

    remarks = db.Column(db.Text, nullable=True)
    legacy_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    # ── Relationships ───────────────────────────────────────────────
    shipment = db.relationship("ShipmentFile", back_populates="containers")
    storage_location = db.relationship("StorageLocation", foreign_keys=[storage_location_id])
    delivery_items = db.relationship("DeliveryNoteItem", back_populates="shipment_container")
    container_return = db.relationship("ContainerReturn", back_populates="shipment_container", uselist=False)


# ── Customer PO (Header) ───────────────────────────────────────────

class CustomerPO(db.Model):
    __tablename__ = "customer_pos"

    id = db.Column(db.Integer, primary_key=True)
    po_no = db.Column(db.String(50), nullable=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True)
    customer_name = db.Column(db.String(200), nullable=True)
    po_date = db.Column(db.Date, nullable=True)
    po_issued_to = db.Column(db.String(50), nullable=True)  # "MPC", "Grace", "Other"
    delivery_terms_id = db.Column(db.Integer, db.ForeignKey("delivery_terms.id"), nullable=True)
    payment_terms_id = db.Column(db.Integer, db.ForeignKey("payment_terms_customer.id"), nullable=True)
    is_closed = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text, nullable=True)
    legacy_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    customer = db.relationship("Customer", foreign_keys=[customer_id])
    delivery_term = db.relationship("DeliveryTerm", foreign_keys=[delivery_terms_id])
    payment_term = db.relationship("PaymentTermCustomer", foreign_keys=[payment_terms_id])
    items = db.relationship("CustomerPOItem", back_populates="customer_po", cascade="all, delete-orphan")


# ── Customer PO Item ────────────────────────────────────────────────

class CustomerPOItem(db.Model):
    __tablename__ = "customer_po_items"

    id = db.Column(db.Integer, primary_key=True)
    customer_po_id = db.Column(db.Integer, db.ForeignKey("customer_pos.id"), nullable=False)
    item_no = db.Column(db.Integer, nullable=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    product_name = db.Column(db.String(200), nullable=True)
    affiliate_id = db.Column(db.Integer, db.ForeignKey("customer_addresses.id"), nullable=True)
    qty = db.Column(db.Float, nullable=True)
    uom = db.Column(db.String(30), nullable=True)
    unit_price = db.Column(db.Float, nullable=True)
    currency = db.Column(db.String(10), nullable=True)
    vat_percent = db.Column(db.Float, default=0)
    vat_value = db.Column(db.Float, default=0)
    total_value = db.Column(db.Float, nullable=True)
    total_value_inc_vat = db.Column(db.Float, nullable=True)
    packing = db.Column(db.String(100), nullable=True)
    delivery_date = db.Column(db.Date, nullable=True)
    sap_code = db.Column(db.String(50), nullable=True)
    so_number = db.Column(db.String(50), nullable=True)
    contract_no = db.Column(db.String(50), nullable=True)
    remarks = db.Column(db.Text, nullable=True)

    customer_po = db.relationship("CustomerPO", back_populates="items")
    product = db.relationship("Product", foreign_keys=[product_id])
    affiliate = db.relationship("CustomerAddress", foreign_keys=[affiliate_id])


# ── Delivery Note ──────────────────────────────────────────────────

class DeliveryNote(db.Model):
    __tablename__ = "delivery_notes"

    id = db.Column(db.Integer, primary_key=True)
    dn_number = db.Column(db.String(20), nullable=True, index=True)
    delivery_date = db.Column(db.Date, nullable=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True)
    customer_name = db.Column(db.String(200), nullable=True)
    affiliate_id = db.Column(db.Integer, db.ForeignKey("customer_addresses.id"), nullable=True)
    transporter_id = db.Column(db.Integer, db.ForeignKey("transporters.id"), nullable=True)
    customer_po_id = db.Column(db.Integer, db.ForeignKey("customer_pos.id"), nullable=True)
    po_item_no = db.Column(db.Integer, nullable=True)
    so_number = db.Column(db.String(50), nullable=True)
    total_qty = db.Column(db.Float, nullable=True)
    gp_docs_required = db.Column(db.Boolean, default=False)
    packing = db.Column(db.String(100), nullable=True)
    remarks = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(30), default="Delivered")
    # Status: Draft / Delivered / Invoiced / Reversed
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    customer = db.relationship("Customer", foreign_keys=[customer_id])
    affiliate = db.relationship("CustomerAddress", foreign_keys=[affiliate_id])
    transporter = db.relationship("Transporter", foreign_keys=[transporter_id])
    customer_po = db.relationship("CustomerPO", foreign_keys=[customer_po_id])
    creator = db.relationship("User", foreign_keys=[created_by])
    items = db.relationship("DeliveryNoteItem", back_populates="delivery_note", cascade="all, delete-orphan")


# ── Delivery Note Item ─────────────────────────────────────────────

class DeliveryNoteItem(db.Model):
    __tablename__ = "delivery_note_items"

    id = db.Column(db.Integer, primary_key=True)
    delivery_note_id = db.Column(db.Integer, db.ForeignKey("delivery_notes.id"), nullable=False)
    shipment_container_id = db.Column(db.Integer, db.ForeignKey("shipment_containers.id"), nullable=True)
    sf_number = db.Column(db.String(20), nullable=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    product_name = db.Column(db.String(200), nullable=True)
    container_no = db.Column(db.String(50), nullable=True)
    qty = db.Column(db.Float, nullable=True)
    uom = db.Column(db.String(30), nullable=True)
    storage_location_id = db.Column(db.Integer, db.ForeignKey("storage_locations.id"), nullable=True)
    packing = db.Column(db.String(100), nullable=True)
    remarks = db.Column(db.Text, nullable=True)

    delivery_note = db.relationship("DeliveryNote", back_populates="items")
    shipment_container = db.relationship("ShipmentContainer", back_populates="delivery_items")
    product = db.relationship("Product", foreign_keys=[product_id])
    storage_location = db.relationship("StorageLocation", foreign_keys=[storage_location_id])


# ── Container Return ───────────────────────────────────────────────

class ContainerReturn(db.Model):
    __tablename__ = "container_returns"

    id = db.Column(db.Integer, primary_key=True)
    shipment_container_id = db.Column(db.Integer, db.ForeignKey("shipment_containers.id"), unique=True, nullable=False)
    container_no = db.Column(db.String(50), nullable=True)
    sf_number = db.Column(db.String(20), nullable=True)
    arrival_to_port_date = db.Column(db.Date, nullable=True)
    empty_pickup_date = db.Column(db.Date, nullable=True)
    empty_pickup_notified = db.Column(db.Boolean, default=False)
    return_terminal_id = db.Column(db.Integer, db.ForeignKey("return_terminals.id"), nullable=True)
    eir_no = db.Column(db.String(50), nullable=True)
    container_return_date = db.Column(db.Date, nullable=True)
    return_complete = db.Column(db.Boolean, default=False)
    is_iso_tank = db.Column(db.Boolean, default=False)
    rental_fee_amount = db.Column(db.Float, nullable=True)
    rental_fee_claimed = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    shipment_container = db.relationship("ShipmentContainer", back_populates="container_return")
    return_terminal = db.relationship("ReturnTerminal", foreign_keys=[return_terminal_id])


# ── Commission Tracking ────────────────────────────────────────────

class CommissionTracking(db.Model):
    __tablename__ = "commission_tracking"

    id = db.Column(db.Integer, primary_key=True)
    delivery_note_id = db.Column(db.Integer, db.ForeignKey("delivery_notes.id"), nullable=True)
    shipment_container_id = db.Column(db.Integer, db.ForeignKey("shipment_containers.id"), nullable=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    qty_delivered = db.Column(db.Float, nullable=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True)

    # ── Commission ──────────────────────────────────────────────────
    commission_calc_received = db.Column(db.Boolean, default=False)
    commission_calc_date = db.Column(db.Date, nullable=True)
    commission_amount = db.Column(db.Float, nullable=True)
    commission_invoice_no = db.Column(db.String(50), nullable=True)
    commission_invoice_submitted = db.Column(db.Boolean, default=False)
    commission_invoice_date = db.Column(db.Date, nullable=True)

    # ── Handling Fee ────────────────────────────────────────────────
    handling_fee_amount = db.Column(db.Float, nullable=True)
    handling_invoice_no = db.Column(db.String(50), nullable=True)
    handling_invoice_submitted = db.Column(db.Boolean, default=False)
    handling_invoice_date = db.Column(db.Date, nullable=True)

    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    delivery_note = db.relationship("DeliveryNote", foreign_keys=[delivery_note_id])
    shipment_container = db.relationship("ShipmentContainer", foreign_keys=[shipment_container_id])
    product = db.relationship("Product", foreign_keys=[product_id])
    customer = db.relationship("Customer", foreign_keys=[customer_id])
    supplier = db.relationship("Supplier", foreign_keys=[supplier_id])


# ── Shipment Payment Tracking ──────────────────────────────────────

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


# ── Broker Cover ───────────────────────────────────────────────────

class BrokerCover(db.Model):
    __tablename__ = "broker_covers"

    id = db.Column(db.Integer, primary_key=True)
    shipment_id = db.Column(db.Integer, db.ForeignKey("shipment_files.id"), nullable=False)
    broker_id = db.Column(db.Integer, db.ForeignKey("brokers.id"), nullable=True)
    cover_date = db.Column(db.Date, nullable=True)
    doc_count = db.Column(db.Integer, nullable=True)
    fcl_count = db.Column(db.Integer, nullable=True)

    # ── Document Originals & Copies ─────────────────────────────────
    bol_originals = db.Column(db.Integer, default=0)
    bol_copies = db.Column(db.Integer, nullable=True)
    invoice_originals = db.Column(db.Integer, default=0)
    invoice_copies = db.Column(db.Integer, nullable=True)
    coo_originals = db.Column(db.Integer, default=0)
    coo_copies = db.Column(db.Integer, default=0)
    packing_list_originals = db.Column(db.Integer, default=0)
    packing_list_copies = db.Column(db.Integer, nullable=True)
    insurance_originals = db.Column(db.Integer, default=0)
    insurance_copies = db.Column(db.Integer, default=0)
    coa_copies = db.Column(db.Integer, nullable=True)
    other_docs = db.Column(db.Text, nullable=True)

    # ── Customer PO Details ─────────────────────────────────────────
    show_customer_po_details = db.Column(db.Boolean, default=False)

    # ── Courier ─────────────────────────────────────────────────────
    courier_name = db.Column(db.String(100), nullable=True)
    courier_tracking = db.Column(db.String(100), nullable=True)
    courier_date = db.Column(db.Date, nullable=True)
    send_via_dhl = db.Column(db.Boolean, default=False)
    dhl_tracking = db.Column(db.String(100), nullable=True)

    notes = db.Column(db.Text, nullable=True)
    legacy_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    shipment = db.relationship("ShipmentFile", back_populates="broker_covers")
    broker = db.relationship("Broker", foreign_keys=[broker_id])


# ── Customer Contract ──────────────────────────────────────────────

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


# ── Audit Log ──────────────────────────────────────────────────────

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
