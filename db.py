"""Database access: read-only for analysis, one guarded write path for approved invoices."""
import os
import sqlite3

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("FINPILOT_DB", os.path.join(HERE, "data", "finpilot.db"))


def ro():
    if not os.path.exists(DB):
        raise RuntimeError("Database not found. Run `python seed_db.py` first.")
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True)


def query(sql: str, params: tuple = ()) -> pd.DataFrame:
    with ro() as con:
        return pd.read_sql_query(sql, con, params=params)


def schema_text() -> str:
    with ro() as con:
        rows = con.execute("SELECT sql FROM sqlite_master WHERE type='table'").fetchall()
        cats = [r[0] for r in con.execute("SELECT DISTINCT category FROM transactions ORDER BY 1")]
        vendors = [r[0] for r in con.execute("SELECT DISTINCT vendor FROM transactions WHERE vendor IS NOT NULL ORDER BY 1")]
    text = "\n".join(r[0] for r in rows)
    text += "\n\nExact values of transactions.category: " + ", ".join(cats)
    text += "\nExact values of transactions.vendor: " + ", ".join(vendors)
    return text


def monthly() -> pd.DataFrame:
    df = query("""SELECT substr(date,1,7) AS month,
                         SUM(CASE WHEN type='income'  THEN amount ELSE 0 END) AS revenue,
                         SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) AS expenses
                  FROM transactions GROUP BY month ORDER BY month""")
    df["profit"] = df.revenue - df.expenses
    df["margin_pct"] = (100 * df.profit / df.revenue).round(1)
    return df.round(2)


def insert_invoice(inv: dict, status: str = "approved"):
    with sqlite3.connect(DB) as con:
        con.execute("INSERT INTO invoices VALUES (?,?,?,?,?,?,?,?)",
                    (inv["invoice_no"], inv["vendor"], inv["invoice_date"], inv["due_date"],
                     inv["subtotal"], inv["tax"], inv["total"], status))
