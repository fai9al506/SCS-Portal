from datetime import date, datetime, timezone
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


class AppSetting(db.Model):
    """Values Access had hard-coded in VBA/queries (rates, bank details, e-mail lists) — decision B7.
    Edited by admins on Admin > Other lists > Settings. Read with services.settings.get()."""
    __tablename__ = "app_settings"
    __access_table__ = "Settings"   # name used in the audit log (not an Access table)
    id = db.Column(db.Integer, primary_key=True)
    Key = db.Column("key", db.String(100), unique=True, nullable=False)
    Value = db.Column("value", db.Text)
    Description = db.Column("description", db.String(255))


# ── SCS tables (mirror of Access back-end) ─────────────────────────
# SCS data tables: an exact mirror of the Access back-end (SCS Database.accdb).
# 
# Python attribute names = Access field names (so the Access spec reads 1:1).
# Column names = snake_case. ACCESS_FIELDS maps each model to its Access table/fields for import.
# Natural-key masters (e.g. Customers.CusName) get a surrogate `id` plus a unique key, like Access.
# Access "Required" rules on non-key fields were added after some rows existed (e.g. 2 customer POs
# have no PODate), so the database accepts NULL there and the screens enforce the rule instead.


class Brokers(db.Model):
    __tablename__ = "brokers"
    __access_table__ = "Brokers"
    id = db.Column(db.Integer, primary_key=True)
    BrokerName = db.Column("broker_name", db.String(255), unique=True, nullable=False)
    BrokerFullName = db.Column("broker_full_name", db.String(255))
    BrokerAdd1 = db.Column("broker_add1", db.String(255))
    BrokerAdd2 = db.Column("broker_add2", db.String(255))
    BrokerAdd3Tel = db.Column("broker_add3_tel", db.String(255))
    BrokerAdd4Mob = db.Column("broker_add4_mob", db.String(255))
    BrokerRepName = db.Column("broker_rep_name", db.String(255))
    BrokerEmails = db.Column("broker_emails", db.String(255))


class ClearanceStatus(db.Model):
    __tablename__ = "clearance_status"
    __access_table__ = "ClearanceStatus"
    id = db.Column(db.Integer, primary_key=True)
    ClearanceStatus = db.Column("clearance_status", db.String(255))
    SN = db.Column("sn", db.Integer, default=0)


class Currency(db.Model):
    __tablename__ = "currency"
    __access_table__ = "Currency"
    id = db.Column(db.Integer, primary_key=True)
    Currency = db.Column("currency", db.String(255), unique=True, nullable=False)


class CustomerAdd(db.Model):
    __tablename__ = "customer_add"
    __access_table__ = "CustomerAdd"
    id = db.Column(db.Integer, primary_key=True)
    Customer = db.Column("customer", db.String(255))
    CustomerPlant = db.Column("customer_plant", db.String(255))
    CusAdd1 = db.Column("cus_add1", db.String(255))
    CusAdd2 = db.Column("cus_add2", db.String(255))
    CusCntName = db.Column("cus_cnt_name", db.String(255))
    CusCntTel = db.Column("cus_cnt_tel", db.String(255))
    CusCntMob = db.Column("cus_cnt_mob", db.String(255))


class CustomerContracts(db.Model):
    __tablename__ = "customer_contracts"
    __access_table__ = "CustomerContracts"
    id = db.Column(db.Integer, primary_key=True)
    CusContractNo = db.Column("cus_contract_no", db.String(255), unique=True, nullable=False)
    CusName = db.Column("cus_name", db.String(255))
    ProductName = db.Column("product_name", db.String(50))
    Qty = db.Column("qty", db.Float, default=0)
    EffictiveDate = db.Column("effictive_date", db.Date)
    ExpiryDate = db.Column("expiry_date", db.Date)
    UnitPrice = db.Column("unit_price", db.Float, default=0)


class Customers(db.Model):
    __tablename__ = "customers"
    __access_table__ = "Customers"
    id = db.Column(db.Integer, primary_key=True)
    CusName = db.Column("cus_name", db.String(255), unique=True, nullable=False)
    SAPID = db.Column("sapid", db.String(255))


class CustomersPO(db.Model):
    __tablename__ = "customers_po"
    __access_table__ = "CustomersPO"
    ID = db.Column("id", db.Integer, primary_key=True)
    CusPONo = db.Column("cus_po_no", db.String(255))
    ItemNo = db.Column("item_no", db.Integer, default=1)
    POIssuedTo = db.Column("po_issued_to", db.String(255))
    Product = db.Column("product", db.String(50))
    PODate = db.Column("po_date", db.Date)
    Affiliate = db.Column("affiliate", db.String(255))
    POQty = db.Column("po_qty", db.Float, default=0)
    DeliveryTerms = db.Column("delivery_terms", db.String(255))
    PaymentTerms = db.Column("payment_terms", db.String(255))
    Curr = db.Column("curr", db.String(255))
    UnitPrice = db.Column("unit_price", db.Float, default=0)
    PerUOM = db.Column("per_uom", db.String(255))
    VAT = db.Column("vat", db.Float, default=0)
    VATValue = db.Column("vat_value", db.Float, db.Computed("unit_price * po_qty * vat", persisted=True))
    Packing = db.Column("packing", db.String(255))
    POValue = db.Column("po_value", db.Float, db.Computed("unit_price * po_qty", persisted=True))
    POValueWVAT = db.Column("po_value_wvat", db.Float, db.Computed("unit_price * po_qty + unit_price * po_qty * vat", persisted=True))
    SONo = db.Column("so_no", db.String(255))
    ContractNo = db.Column("contract_no", db.String(255))
    DeliveryDate = db.Column("delivery_date", db.Date)
    Remarks = db.Column("remarks", db.String(255))
    Closed = db.Column("closed", db.Boolean, default=False, nullable=False)


class DeliveryTerms(db.Model):
    __tablename__ = "delivery_terms"
    __access_table__ = "DeliveryTerms"
    id = db.Column(db.Integer, primary_key=True)
    DeliveryTerm = db.Column("delivery_term", db.String(255), unique=True, nullable=False)


class InternalContacts(db.Model):
    __tablename__ = "internal_contacts"
    __access_table__ = "InternalContacts"
    id = db.Column(db.Integer, primary_key=True)
    Group = db.Column("group", db.String(255), unique=True, nullable=False)
    Groupemails = db.Column("groupemails", db.String(255))


class Packing(db.Model):
    __tablename__ = "packing"
    __access_table__ = "Packing"
    id = db.Column(db.Integer, primary_key=True)
    PackinMode = db.Column("packin_mode", db.String(255), unique=True, nullable=False)


class PaymentTerms(db.Model):
    __tablename__ = "payment_terms"
    __access_table__ = "Payment Terms"
    id = db.Column(db.Integer, primary_key=True)
    PaymentTerm = db.Column("payment_term", db.String(255), unique=True, nullable=False)


class PayTermsCus(db.Model):
    __tablename__ = "pay_terms_cus"
    __access_table__ = "PayTermsCus"
    id = db.Column(db.Integer, primary_key=True)
    PayTermCus = db.Column("pay_term_cus", db.String(255), unique=True, nullable=False)


class PermitReq(db.Model):
    __tablename__ = "permit_req"
    __access_table__ = "PermitReq"
    ID = db.Column("id", db.Integer, primary_key=True, nullable=False)
    PermitReq = db.Column("permit_req", db.String(255))


class Permits(db.Model):
    __tablename__ = "permits"
    __access_table__ = "Permits"
    ID = db.Column("id", db.Integer, primary_key=True)
    PermitNo = db.Column("permit_no", db.String(255))
    ProductName = db.Column("product_name", db.String(50))
    HSCode = db.Column("hs_code", db.String(255))
    NameinCustoms = db.Column("namein_customs", db.String(255))
    PermitRequirement = db.Column("permit_requirement", db.String(255))
    DutyPercent = db.Column("duty_percent", db.Float, default=0)
    Qty = db.Column("qty", db.Numeric(18, 3), default=0)
    ExpiryDate = db.Column("expiry_date", db.Date)


class POIssuedToCompanies(db.Model):
    __tablename__ = "poissued_to_companies"
    __access_table__ = "POIssuedToCompanies"
    id = db.Column(db.Integer, primary_key=True)
    CompanyName = db.Column("company_name", db.String(255), unique=True, nullable=False)


class PortOfDestinations(db.Model):
    __tablename__ = "port_of_destinations"
    __access_table__ = "Port of Destinations"
    id = db.Column(db.Integer, primary_key=True)
    PortOfDistination = db.Column("port_of_distination", db.String(255), unique=True, nullable=False)


class ProductGroup(db.Model):
    __tablename__ = "product_group"
    __access_table__ = "ProductGroup"
    ID = db.Column("id", db.Integer, primary_key=True, nullable=False)
    ProductGroup = db.Column("product_group", db.String(255))


class Products(db.Model):
    __tablename__ = "products"
    __access_table__ = "Products"
    id = db.Column(db.Integer, primary_key=True)
    ProductName = db.Column("product_name", db.String(50), unique=True, nullable=False)
    ProductGroup = db.Column("product_group", db.String(255))
    SAPName = db.Column("sap_name", db.String(255))


class ReturningTerminal(db.Model):
    __tablename__ = "returning_terminal"
    __access_table__ = "ReturningTerminal"
    id = db.Column(db.Integer, primary_key=True)
    Terminal = db.Column("terminal", db.String(255), unique=True, nullable=False)


class SF(db.Model):
    __tablename__ = "sf"
    __access_table__ = "SF"
    UID = db.Column("uid", db.Integer, primary_key=True, nullable=False)
    EntryDate = db.Column("entry_date", db.Date, default=date.today)
    SF = db.Column("sf", db.Integer, default=0)
    MPCPONo = db.Column("mpcpo_no", db.String(10))
    MPCPOItemNo = db.Column("mpcpo_item_no", db.String(255))
    Supplier = db.Column("supplier", db.String(255))
    Product = db.Column("product", db.String(255))
    SFQty = db.Column("sf_qty", db.Numeric(18, 3), default=0)
    UOM = db.Column("uom", db.String(255))
    Packing = db.Column("packing", db.String(255), default="Container")
    ContainerNo = db.Column("container_no", db.String(255))
    ETD = db.Column("etd", db.Date)
    ETA = db.Column("eta", db.Date)
    POD = db.Column("pod", db.String(255))
    Status = db.Column("status", db.String(255))
    IntendedCustomer = db.Column("intended_customer", db.String(255))
    IntendedCustomerPO = db.Column("intended_customer_po", db.String(255))
    DocsToBroker = db.Column("docs_to_broker", db.Date)
    Broker = db.Column("broker", db.String(255))
    PermitNo = db.Column("permit_no", db.String(255))
    ShippingLine = db.Column("shipping_line", db.String(255))
    BOL = db.Column("bol", db.String(255))
    SupplierInv = db.Column("supplier_inv", db.String(255))
    SupplierInvDate = db.Column("supplier_inv_date", db.Date)
    UnitPrice = db.Column("unit_price", db.Float, default=0)
    ACurr = db.Column("a_curr", db.String(255))
    InvAmount = db.Column("inv_amount", db.Float, db.Computed("sf_qty * unit_price", persisted=True))
    Remarks = db.Column("remarks", db.String(255))
    BayanNo = db.Column("bayan_no", db.String(255))
    ClearanceDate = db.Column("clearance_date", db.Date)
    StorageLoc = db.Column("storage_loc", db.String(255))
    MPCGRN = db.Column("mpcgrn", db.String(255))
    MPCGRDate = db.Column("mpcgr_date", db.Date)
    GRRemarks = db.Column("gr_remarks", db.String(255))
    DeliveredOn = db.Column("delivered_on", db.Date)
    DeliveredTo = db.Column("delivered_to", db.String(255))
    DeliveredToPlant = db.Column("delivered_to_plant", db.String(255))
    DeliveredToAdd1 = db.Column("delivered_to_add1", db.String(255))
    DeliveredToAdd2 = db.Column("delivered_to_add2", db.String(255))
    DeliveredToContactName = db.Column("delivered_to_contact_name", db.String(255))
    DeliveredToContactTel = db.Column("delivered_to_contact_tel", db.String(255))
    DeliveredToContactMob = db.Column("delivered_to_contact_mob", db.String(255))
    DeliveredTransporter = db.Column("delivered_transporter", db.String(255))
    DeliveredPO = db.Column("delivered_po", db.String(255))
    DeliveredPOItem = db.Column("delivered_po_item", db.Integer)
    DeliveredSO = db.Column("delivered_so", db.Integer)
    DeliveredPacking = db.Column("delivered_packing", db.String(255))
    DeliveryRemarks = db.Column("delivery_remarks", db.String(255))
    SAPDNNo = db.Column("sapdn_no", db.String(255))
    InvNo = db.Column("inv_no", db.String(255))
    InvDate = db.Column("inv_date", db.Date)
    DetentionInv = db.Column("detention_inv", db.String(255))
    DetentionInvSubmitted = db.Column("detention_inv_submitted", db.Boolean, default=False, nullable=False)
    CommissionActualInvValue = db.Column("commission_actual_inv_value", db.Numeric(18, 3), default=0)
    CommissionActualInv = db.Column("commission_actual_inv", db.String(255))
    CommissionInvSubmitted = db.Column("commission_inv_submitted", db.Boolean, default=False, nullable=False)
    ServiceInv = db.Column("service_inv", db.String(255))
    ServiceInvSubmitted = db.Column("service_inv_submitted", db.Boolean, default=False, nullable=False)
    CusGR = db.Column("cus_gr", db.String(255))
    DateofArrivaltoPort = db.Column("dateof_arrivalto_port", db.Date)
    EmptyPickNotified = db.Column("empty_pick_notified", db.Date)
    EmptyPickDate = db.Column("empty_pick_date", db.Date)
    EmptyReturnDate = db.Column("empty_return_date", db.Date)
    EIRNo = db.Column("eir_no", db.String(255))
    ReturnTerminal = db.Column("return_terminal", db.String(255))
    ReturnIsDone = db.Column("return_is_done", db.Boolean, default=False, nullable=False)


class SFBrokerCover(db.Model):
    __tablename__ = "sf_broker_cover"
    __access_table__ = "SF_BrokerCover"
    ID = db.Column("id", db.Integer, primary_key=True, nullable=False)
    SFNo = db.Column("sf_no", db.Integer)
    Product = db.Column("product", db.String(255))
    SFQty = db.Column("sf_qty", db.Numeric(18, 3), default=0)
    NoFCL = db.Column("no_fcl", db.Numeric(18, 3), default=0)
    UOM = db.Column("uom", db.String(255))
    ETD = db.Column("etd", db.Date)
    ETA = db.Column("eta", db.Date)
    POD = db.Column("pod", db.String(255))
    DocsToBroker = db.Column("docs_to_broker", db.DateTime)
    Broker = db.Column("broker", db.String(255))
    BrokerFullName = db.Column("broker_full_name", db.String(255))
    BrokerAdd1 = db.Column("broker_add1", db.String(255))
    BrokerAdd2 = db.Column("broker_add2", db.String(255))
    BrokerAdd3Tel = db.Column("broker_add3_tel", db.String(255))
    BrokerAdd4Mob = db.Column("broker_add4_mob", db.String(255))
    BrokerRepName = db.Column("broker_rep_name", db.String(255))
    BrokerEmails = db.Column("broker_emails", db.String(255))
    PermitNo = db.Column("permit_no", db.String(255))
    ShippingLine = db.Column("shipping_line", db.String(255))
    BOL = db.Column("bol", db.String(255))
    SupplierInv = db.Column("supplier_inv", db.String(255))
    SupplierInvDate = db.Column("supplier_inv_date", db.Date)
    IntendedCustomer = db.Column("intended_customer", db.String(255))
    IntendedCustomerPO = db.Column("intended_customer_po", db.Numeric(18, 0))
    NoofOrgBOL = db.Column("noof_org_bol", db.Integer, default=0)
    NoofCopyBOL = db.Column("noof_copy_bol", db.Integer, default=0)
    NoofOrgInv = db.Column("noof_org_inv", db.Integer, default=0)
    NoofCopyInv = db.Column("noof_copy_inv", db.Integer, default=0)
    NoofOrgCOO = db.Column("noof_org_coo", db.Integer, default=0)
    NoofCopyCOO = db.Column("noof_copy_coo", db.Integer, default=0)
    NoofOrgCOA = db.Column("noof_org_coa", db.Integer, default=0)
    NoofCopyCOA = db.Column("noof_copy_coa", db.Integer, default=0)
    NoofOrgPL = db.Column("noof_org_pl", db.Integer, default=0)
    NoofCopyPL = db.Column("noof_copy_pl", db.Integer, default=0)
    NoofOrgInsurance = db.Column("noof_org_insurance", db.Integer, default=0)
    NoofCopyInsurance = db.Column("noof_copy_insurance", db.Integer, default=0)
    CourierNo = db.Column("courier_no", db.String(255))
    EntryDate = db.Column("entry_date", db.DateTime, default=datetime.now)


class ShipmentsStatus(db.Model):
    __tablename__ = "shipments_status"
    __access_table__ = "ShipmentsStatus"
    ID = db.Column("id", db.Integer, primary_key=True, nullable=False)
    MPCPONo = db.Column("mpcpo_no", db.String(10))
    ItemNo = db.Column("item_no", db.String(255), default="1")
    EntryDate = db.Column("entry_date", db.Date, default=date.today)
    Supplier = db.Column("supplier", db.String(255))
    Product = db.Column("product", db.String(50))
    Qty = db.Column("qty", db.Numeric(18, 3), default=0)
    UOM = db.Column("uom", db.String(255))
    UnitPrice = db.Column("unit_price", db.Float, default=0)
    ACurr = db.Column("a_curr", db.String(255))
    TotalAmount = db.Column("total_amount", db.Float, db.Computed("qty * unit_price", persisted=True))
    ETD = db.Column("etd", db.Date)
    ETA = db.Column("eta", db.Date)
    POD = db.Column("pod", db.String(255))
    PayTerm = db.Column("pay_term", db.String(255))
    FirstPayment = db.Column("first_payment", db.String(255))
    FirstPayFB = db.Column("first_pay_fb", db.String(255))
    FirstPayFBD = db.Column("first_pay_fbd", db.Boolean, default=False, nullable=False)
    SecondPayment = db.Column("second_payment", db.String(255))
    SecondPayFB = db.Column("second_pay_fb", db.String(255))
    SecondPayFBD = db.Column("second_pay_fbd", db.Boolean, default=False, nullable=False)
    PayType = db.Column("pay_type", db.String(243), db.Computed("CASE WHEN first_payment = 'Required' THEN 'Advance' WHEN second_payment = 'Required' THEN 'Balance' ELSE '' END", persisted=True))
    SFNo = db.Column("sf_no", db.Integer)
    DocsTrackingNo = db.Column("docs_tracking_no", db.String(255))
    ClearanceStatus = db.Column("clearance_status", db.String(255))
    Status = db.Column("status", db.String(255), default="Ordered")
    PermitNo = db.Column("permit_no", db.String(255))


class ShippingLines(db.Model):
    __tablename__ = "shipping_lines"
    __access_table__ = "ShippingLines"
    id = db.Column(db.Integer, primary_key=True)
    SLName = db.Column("sl_name", db.String(255), unique=True, nullable=False)


class SStatus(db.Model):
    __tablename__ = "sstatus"
    __access_table__ = "SStatus"
    id = db.Column(db.Integer, primary_key=True)
    Status = db.Column("status", db.String(255), unique=True, nullable=False)


class StorageLoc(db.Model):
    __tablename__ = "storage_loc"
    __access_table__ = "StorageLoc"
    id = db.Column(db.Integer, primary_key=True)
    StorageLocation = db.Column("storage_location", db.String(255), unique=True, nullable=False)
    emails = db.Column("emails", db.String(255))


class Suppliers(db.Model):
    __tablename__ = "suppliers"
    __access_table__ = "Suppliers"
    id = db.Column(db.Integer, primary_key=True)
    SupplierName = db.Column("supplier_name", db.String(255), unique=True, nullable=False)
    SAPNo = db.Column("sap_no", db.String(255))


class Transporters(db.Model):
    __tablename__ = "transporters"
    __access_table__ = "Transporters"
    id = db.Column(db.Integer, primary_key=True)
    TransporterName = db.Column("transporter_name", db.String(255), unique=True, nullable=False)
    emails = db.Column("emails", db.String(255))


class UOM(db.Model):
    __tablename__ = "uom"
    __access_table__ = "UOM"
    id = db.Column(db.Integer, primary_key=True)
    UOM = db.Column("uom", db.String(255), unique=True, nullable=False)


# Access field name -> model attribute, per model (used by the importer).
ACCESS_FIELDS = {
    Brokers: {'BrokerName': 'BrokerName', 'BrokerFullName': 'BrokerFullName', 'BrokerAdd1': 'BrokerAdd1', 'BrokerAdd2': 'BrokerAdd2', 'BrokerAdd3Tel': 'BrokerAdd3Tel', 'BrokerAdd4Mob': 'BrokerAdd4Mob', 'BrokerRepName': 'BrokerRepName', 'BrokerEmails': 'BrokerEmails'},
    ClearanceStatus: {'ClearanceStatus': 'ClearanceStatus', 'SN': 'SN'},
    Currency: {'Currency': 'Currency'},
    CustomerAdd: {'Customer': 'Customer', 'CustomerPlant': 'CustomerPlant', 'CusAdd1': 'CusAdd1', 'CusAdd2': 'CusAdd2', 'CusCntName': 'CusCntName', 'CusCntTel': 'CusCntTel', 'CusCntMob': 'CusCntMob'},
    CustomerContracts: {'CusContractNo': 'CusContractNo', 'CusName': 'CusName', 'ProductName': 'ProductName', 'Qty': 'Qty', 'EffictiveDate': 'EffictiveDate', 'ExpiryDate': 'ExpiryDate', 'UnitPrice': 'UnitPrice'},
    Customers: {'CusName': 'CusName', 'SAPID': 'SAPID'},
    CustomersPO: {'ID': 'ID', 'CusPONo': 'CusPONo', 'ItemNo': 'ItemNo', 'POIssuedTo': 'POIssuedTo', 'Product': 'Product', 'PODate': 'PODate', 'Affiliate': 'Affiliate', 'POQty': 'POQty', 'DeliveryTerms': 'DeliveryTerms', 'PaymentTerms': 'PaymentTerms', 'Curr': 'Curr', 'UnitPrice': 'UnitPrice', 'PerUOM': 'PerUOM', 'VAT': 'VAT', 'VATValue': 'VATValue', 'Packing': 'Packing', 'POValue': 'POValue', 'POValueWVAT': 'POValueWVAT', 'SONo': 'SONo', 'ContractNo': 'ContractNo', 'DeliveryDate': 'DeliveryDate', 'Remarks': 'Remarks', 'Closed': 'Closed'},
    DeliveryTerms: {'DeliveryTerm': 'DeliveryTerm'},
    InternalContacts: {'Group': 'Group', 'Groupemails': 'Groupemails'},
    Packing: {'PackinMode': 'PackinMode'},
    PaymentTerms: {'PaymentTerm': 'PaymentTerm'},
    PayTermsCus: {'PayTermCus': 'PayTermCus'},
    PermitReq: {'ID': 'ID', 'PermitReq': 'PermitReq'},
    Permits: {'ID': 'ID', 'PermitNo': 'PermitNo', 'ProductName': 'ProductName', 'HSCode': 'HSCode', 'NameinCustoms': 'NameinCustoms', 'PermitRequirement': 'PermitRequirement', 'DutyPercent': 'DutyPercent', 'Qty': 'Qty', 'ExpiryDate': 'ExpiryDate'},
    POIssuedToCompanies: {'CompanyName': 'CompanyName'},
    PortOfDestinations: {'Port of Distination': 'PortOfDistination'},
    ProductGroup: {'ID': 'ID', 'ProductGroup': 'ProductGroup'},
    Products: {'ProductName': 'ProductName', 'ProductGroup': 'ProductGroup', 'SAPName': 'SAPName'},
    ReturningTerminal: {'Terminal': 'Terminal'},
    SF: {'UID': 'UID', 'EntryDate': 'EntryDate', 'SF': 'SF', 'MPCPONo': 'MPCPONo', 'MPCPOItemNo': 'MPCPOItemNo', 'Supplier': 'Supplier', 'Product': 'Product', 'SFQty': 'SFQty', 'UOM': 'UOM', 'Packing': 'Packing', 'ContainerNo': 'ContainerNo', 'ETD': 'ETD', 'ETA': 'ETA', 'POD': 'POD', 'Status': 'Status', 'IntendedCustomer': 'IntendedCustomer', 'IntendedCustomerPO': 'IntendedCustomerPO', 'DocsToBroker': 'DocsToBroker', 'Broker': 'Broker', 'PermitNo': 'PermitNo', 'ShippingLine': 'ShippingLine', 'BOL': 'BOL', 'SupplierInv': 'SupplierInv', 'SupplierInvDate': 'SupplierInvDate', 'UnitPrice': 'UnitPrice', 'ACurr': 'ACurr', 'InvAmount': 'InvAmount', 'Remarks': 'Remarks', 'BayanNo': 'BayanNo', 'ClearanceDate': 'ClearanceDate', 'StorageLoc': 'StorageLoc', 'MPCGRN': 'MPCGRN', 'MPCGRDate': 'MPCGRDate', 'GRRemarks': 'GRRemarks', 'DeliveredOn': 'DeliveredOn', 'DeliveredTo': 'DeliveredTo', 'DeliveredToPlant': 'DeliveredToPlant', 'DeliveredToAdd1': 'DeliveredToAdd1', 'DeliveredToAdd2': 'DeliveredToAdd2', 'DeliveredToContactName': 'DeliveredToContactName', 'DeliveredToContactTel': 'DeliveredToContactTel', 'DeliveredToContactMob': 'DeliveredToContactMob', 'DeliveredTransporter': 'DeliveredTransporter', 'DeliveredPO': 'DeliveredPO', 'DeliveredPOItem': 'DeliveredPOItem', 'DeliveredSO': 'DeliveredSO', 'DeliveredPacking': 'DeliveredPacking', 'DeliveryRemarks': 'DeliveryRemarks', 'SAPDNNo': 'SAPDNNo', 'InvNo': 'InvNo', 'InvDate': 'InvDate', 'DetentionInv': 'DetentionInv', 'DetentionInvSubmitted': 'DetentionInvSubmitted', 'CommissionActualInvValue': 'CommissionActualInvValue', 'CommissionActualInv': 'CommissionActualInv', 'CommissionInvSubmitted': 'CommissionInvSubmitted', 'ServiceInv': 'ServiceInv', 'ServiceInvSubmitted': 'ServiceInvSubmitted', 'CusGR': 'CusGR', 'DateofArrivaltoPort': 'DateofArrivaltoPort', 'EmptyPickNotified': 'EmptyPickNotified', 'EmptyPickDate': 'EmptyPickDate', 'EmptyReturnDate': 'EmptyReturnDate', 'EIRNo': 'EIRNo', 'ReturnTerminal': 'ReturnTerminal', 'ReturnIsDone': 'ReturnIsDone'},
    SFBrokerCover: {'ID': 'ID', 'SFNo': 'SFNo', 'Product': 'Product', 'SFQty': 'SFQty', 'NoFCL': 'NoFCL', 'UOM': 'UOM', 'ETD': 'ETD', 'ETA': 'ETA', 'POD': 'POD', 'DocsToBroker': 'DocsToBroker', 'Broker': 'Broker', 'BrokerFullName': 'BrokerFullName', 'BrokerAdd1': 'BrokerAdd1', 'BrokerAdd2': 'BrokerAdd2', 'BrokerAdd3Tel': 'BrokerAdd3Tel', 'BrokerAdd4Mob': 'BrokerAdd4Mob', 'BrokerRepName': 'BrokerRepName', 'BrokerEmails': 'BrokerEmails', 'PermitNo': 'PermitNo', 'ShippingLine': 'ShippingLine', 'BOL': 'BOL', 'SupplierInv': 'SupplierInv', 'SupplierInvDate': 'SupplierInvDate', 'IntendedCustomer': 'IntendedCustomer', 'IntendedCustomerPO': 'IntendedCustomerPO', 'NoofOrgBOL': 'NoofOrgBOL', 'NoofCopyBOL': 'NoofCopyBOL', 'NoofOrgInv': 'NoofOrgInv', 'NoofCopyInv': 'NoofCopyInv', 'NoofOrgCOO': 'NoofOrgCOO', 'NoofCopyCOO': 'NoofCopyCOO', 'NoofOrgCOA': 'NoofOrgCOA', 'NoofCopyCOA': 'NoofCopyCOA', 'NoofOrgPL': 'NoofOrgPL', 'NoofCopyPL': 'NoofCopyPL', 'NoofOrgInsurance': 'NoofOrgInsurance', 'NoofCopyInsurance': 'NoofCopyInsurance', 'CourierNo': 'CourierNo', 'EntryDate': 'EntryDate'},
    ShipmentsStatus: {'ID': 'ID', 'MPCPONo': 'MPCPONo', 'ItemNo': 'ItemNo', 'EntryDate': 'EntryDate', 'Supplier': 'Supplier', 'Product': 'Product', 'Qty': 'Qty', 'UOM': 'UOM', 'UnitPrice': 'UnitPrice', 'ACurr': 'ACurr', 'TotalAmount': 'TotalAmount', 'ETD': 'ETD', 'ETA': 'ETA', 'POD': 'POD', 'PayTerm': 'PayTerm', '1stPayment': 'FirstPayment', '1stPayFB': 'FirstPayFB', '1stPayFBD': 'FirstPayFBD', '2ndPayment': 'SecondPayment', '2ndPayFB': 'SecondPayFB', '2ndPayFBD': 'SecondPayFBD', 'PayType': 'PayType', 'SFNo': 'SFNo', 'DocsTrackingNo': 'DocsTrackingNo', 'ClearanceStatus': 'ClearanceStatus', 'Status': 'Status', 'PermitNo': 'PermitNo'},
    ShippingLines: {'SLName': 'SLName'},
    SStatus: {'Status': 'Status'},
    StorageLoc: {'StorageLocation': 'StorageLocation', 'emails': 'emails'},
    Suppliers: {'Supplier Name': 'SupplierName', 'SAPNo': 'SAPNo'},
    Transporters: {'TransporterName': 'TransporterName', 'emails': 'emails'},
    UOM: {'UOM': 'UOM'},
}
