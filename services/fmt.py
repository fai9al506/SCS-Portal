"""Access display formats and input parsing (Standard, Percent, short date dd-mm-yyyy …)."""
import re
from datetime import date, datetime
from decimal import Decimal

DATE_FMT = "%d-%m-%Y"   # Windows short date on the users' PCs (screenshots: 09-03-2026)


def standard(v, decimals=2):
    """Access Format "Standard": thousands separator, 2 decimals. None -> ''."""
    if v is None or v == "":
        return ""
    return f"{float(v):,.{decimals}f}"


def dollar(v):
    """Access format $#,##0.00;($#,##0.00)."""
    if v is None or v == "":
        return ""
    v = float(v)
    return f"(${-v:,.2f})" if v < 0 else f"${v:,.2f}"


def percent(v):
    if v is None or v == "":
        return ""
    return f"{float(v) * 100:.2f}%"


def short_date(v):
    if v is None or v == "":
        return ""
    if isinstance(v, datetime):
        v = v.date()
    return v.strftime(DATE_FMT)


def long_date(v):
    """Access Long Date, e.g. 'Thursday, 1 October 2026'."""
    if v is None:
        return ""
    return f"{v:%A}, {v.day} {v:%B %Y}"


def general(v):
    """Access General Number: no separators, no trailing zeros (e.g. 1.325, 1.7, 4)."""
    if v is None or v == "":
        return ""
    if isinstance(v, (float, Decimal)):
        f = float(v)
        return str(int(f)) if f == int(f) else repr(f)
    return str(v)


def fmt_value(v, fmt=None):
    """Format a stored value for display in a control."""
    if fmt == "standard":
        return standard(v)
    if fmt == "dollar":
        return dollar(v)
    if fmt == "percent":
        return percent(v)
    if fmt == "int":
        return "" if v is None else str(int(v))
    if isinstance(v, (date, datetime)):
        return short_date(v)
    if isinstance(v, bool):
        return v
    if isinstance(v, (float, Decimal)):
        return general(v)
    return "" if v is None else v


class ParseError(ValueError):
    pass


MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def parse_date(s):
    """Dates as Access accepts them: 15-10-2026, 15/10/26, 15.10.2026, 2026-10-15, and short forms that take
    the current year: 15-10, 15/10, 15 Oct, Oct 15, 15-Oct-2026."""
    s = (s or "").strip()
    if not s:
        return None
    for f in ("%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%Y-%m-%d", "%d-%m-%y", "%d/%m/%y", "%d.%m.%y"):
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            pass
    parts = [p for p in re.split(r"[\s\-/.,]+", s.lower()) if p]
    try:
        year = date.today().year
        if len(parts) in (2, 3):
            if parts[0].isdigit() and parts[1].isdigit():                    # 15-10 / 15-10-2026
                d, m = int(parts[0]), int(parts[1])
            elif parts[0].isdigit() and parts[1][:3] in MONTHS:              # 15 Oct / 15-Oct-2026
                d, m = int(parts[0]), MONTHS[parts[1][:3]]
            elif parts[0][:3] in MONTHS and parts[1].isdigit():              # Oct 15 / Oct 15 2026
                d, m = int(parts[1]), MONTHS[parts[0][:3]]
            else:
                raise ValueError
            if len(parts) == 3:
                year = int(parts[2]) + (2000 if len(parts[2]) <= 2 else 0)
            return date(year, m, d)
    except ValueError:
        pass
    raise ParseError("The value you entered isn't valid for this field.\n\nFor example, you may have entered text "
                     "in a numeric field or a number that is larger than the FieldSize setting permits.")


def parse_number(s, fmt=None):
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return s
    s = str(s).strip()
    if not s:
        return None
    neg = s.startswith("(") and s.endswith(")")
    pct = s.endswith("%")
    t = re.sub(r"[,$()%\s]", "", s)
    try:
        v = float(t)
    except ValueError:
        raise ParseError("The value you entered isn't valid for this field.\n\nFor example, you may have entered text in a numeric field or a number that is larger than the FieldSize setting permits.")
    if neg:
        v = -v
    if pct:
        v = v / 100
    return v
