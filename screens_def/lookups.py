"""Row sources shared by many screens (Access combo boxes)."""
from sqlalchemy import func

from extensions import db
from models import (
    ClearanceStatus, Currency, Customers, InternalContacts, Packing, PaymentTerms, PayTermsCus, PermitReq,
    PortOfDestinations, Products, ReturningTerminal, ShippingLines, SStatus, StorageLoc, Suppliers, Transporters,
    UOM, Brokers, DeliveryTerms, POIssuedToCompanies, CustomerAdd,
)


def _col(model, attr, order=None):
    col = getattr(model, attr)
    return [r[0] for r in db.session.query(col).order_by(order if order is not None else col).all()]


def suppliers(p=None): return _col(Suppliers, "SupplierName")
def products(p=None): return _col(Products, "ProductName")
def customers(p=None): return _col(Customers, "CusName")
def uoms(p=None): return _col(UOM, "UOM")
def currencies(p=None): return _col(Currency, "Currency")
def ports(p=None): return _col(PortOfDestinations, "PortOfDistination")
def pay_terms(p=None): return _col(PaymentTerms, "PaymentTerm")
def pay_terms_cus(p=None): return _col(PayTermsCus, "PayTermCus")
def statuses(p=None): return _col(SStatus, "Status")
def packing(p=None): return _col(Packing, "PackinMode")
def shipping_lines(p=None): return _col(ShippingLines, "SLName")
def brokers(p=None): return _col(Brokers, "BrokerName")
def transporters(p=None): return _col(Transporters, "TransporterName")
def storage_locations(p=None): return _col(StorageLoc, "StorageLocation")
def return_terminals(p=None): return _col(ReturningTerminal, "Terminal")
def delivery_terms(p=None): return _col(DeliveryTerms, "DeliveryTerm")
def po_issued_to(p=None): return _col(POIssuedToCompanies, "CompanyName")
def permit_reqs(p=None): return _col(PermitReq, "PermitReq", PermitReq.ID)
def clearance_statuses(p=None):
    return [[c.ClearanceStatus, str(c.SN)] for c in ClearanceStatus.query.order_by(ClearanceStatus.SN)]


PAYMENT_STATES = ["NA", "Required", "Done"]


def group_emails(group):
    """InternalContacts.Groupemails for a group (DLookup in the Access VBA)."""
    row = InternalContacts.query.filter(func.lower(InternalContacts.Group) == group.lower()).first()
    return (row.Groupemails or "") if row else ""
