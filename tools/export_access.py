"""Export every table of the SCS Access back-end to one gzipped JSON file.

Run on a Windows PC that has the Access ODBC driver. First set the Access password
(PowerShell: $env:SCS_ACCESS_PWD = "..."), then:
    python tools/export_access.py "C:\\path\\SCS Database.accdb" scs_data.json.gz

Then upload the .json.gz on the portal: Admin > Import Access Data.
The file contains business data — do not commit it to git.
"""
import datetime
import decimal
import gzip
import json
import os
import sys

import pyodbc

PASSWORD = os.environ.get("SCS_ACCESS_PWD")  # the Access database password; never put it in this file


def _value(v):
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.isoformat()
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, bytes):
        return None
    return v


def export(accdb_path, out_path):
    conn = pyodbc.connect(
        "DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
        f"DBQ={os.path.abspath(accdb_path)};PWD={PASSWORD}"
    )
    cur = conn.cursor()
    tables = [t.table_name for t in cur.tables(tableType="TABLE")]
    data = {"exported_at": datetime.datetime.now().isoformat(), "source": os.path.basename(accdb_path), "tables": {}}
    for table in tables:
        cols = [c.column_name for c in cur.columns(table=table)]
        # Large Number (BigInt, reported as CHAR) and Decimal fields are mis-read by the ODBC driver:
        # cast them to Double
        bigint = {c.column_name for c in cur.columns(table=table)
                  if c.type_name.upper() in ("CHAR", "BIGINT", "DECIMAL", "NUMERIC")}
        select = ", ".join(f"IIf(IsNull([{c}]), Null, CDbl([{c}])) AS [x{i}]" if c in bigint else f"[{c}]"
                           for i, c in enumerate(cols))
        rows = cur.execute(f"SELECT {select} FROM [{table}]").fetchall()
        data["tables"][table] = [{c: _value(v) for c, v in zip(cols, r)} for r in rows]
        print(f"{table}: {len(rows)} rows")
    conn.close()
    with gzip.open(out_path, "wt", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"Saved {out_path} ({os.path.getsize(out_path) // 1024} KB)")


if __name__ == "__main__":
    if len(sys.argv) != 3 or not PASSWORD:
        sys.exit(__doc__)
    export(sys.argv[1], sys.argv[2])
