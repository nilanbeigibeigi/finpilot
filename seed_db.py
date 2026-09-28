"""Create data/finpilot.db: 12 months of synthetic finances for Saffron Market (Oct 2025 - Sep 2026).

Planted patterns (so the analysis has real things to find):
  - Sales peak before Yalda (Dec) and Nowruz (Mar)
  - Supplier costs jump in Feb 2026 (a nut & saffron price increase)
  - Utilities are higher in winter
  - A forgotten software subscription ("CloudBackup Pro") starts in May 2026
"""
import datetime as dt
import os
import random
import sqlite3

random.seed(7)
HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("FINPILOT_DB", os.path.join(HERE, "data", "finpilot.db"))
START, END = dt.date(2025, 10, 1), dt.date(2026, 9, 30)

SCHEMA = """
CREATE TABLE vendors (
  name TEXT PRIMARY KEY,
  category TEXT NOT NULL,              -- Suppliers, Utilities, Services, Software, ...
  expected_tax_rate REAL NOT NULL,     -- set by the business for invoice checks
  payment_terms_days INTEGER NOT NULL
);
CREATE TABLE transactions (
  id INTEGER PRIMARY KEY,
  date TEXT NOT NULL,                  -- YYYY-MM-DD
  type TEXT NOT NULL CHECK (type IN ('income','expense')),
  category TEXT NOT NULL,
  vendor TEXT,                         -- NULL for sales
  description TEXT,
  amount REAL NOT NULL                 -- always positive; type says the direction
);
CREATE TABLE invoices (
  invoice_no TEXT NOT NULL,
  vendor TEXT NOT NULL,
  invoice_date TEXT NOT NULL,
  due_date TEXT NOT NULL,
  subtotal REAL NOT NULL,
  tax REAL NOT NULL,
  total REAL NOT NULL,
  status TEXT NOT NULL,                -- paid / approved
  PRIMARY KEY (vendor, invoice_no)
);
CREATE INDEX idx_tx_date ON transactions(date);
"""

VENDORS = [
    ("Golden Grain Imports", "Suppliers", 0.0, 30),
    ("Kerman Nuts Ltd.", "Suppliers", 0.0, 30),
    ("Zarrin Saffron Co.", "Suppliers", 0.0, 15),
    ("Pacific Dairy", "Suppliers", 0.0, 14),
    ("Fraser Valley Produce", "Suppliers", 0.0, 7),
    ("SparkleClean Services", "Services", 0.12, 30),
    ("CoolTech Refrigeration", "Repairs", 0.12, 15),
    ("BC Hydro", "Utilities", 0.05, 21),
    ("FortisBC Gas", "Utilities", 0.05, 21),
    ("Telus Business", "Utilities", 0.12, 30),
    ("Kingsway Properties", "Rent", 0.05, 1),
    ("SquarePOS", "Software", 0.12, 1),
    ("QuickLedger", "Software", 0.12, 1),
    ("CloudBackup Pro", "Software", 0.12, 1),
    ("Coastal Insurance", "Insurance", 0.0, 30),
    ("Local Ads Media", "Marketing", 0.12, 30),
]


def season(d):
    m = 1.0
    if dt.date(2025, 12, 10) <= d <= dt.date(2025, 12, 21): m *= 1.8
    if dt.date(2026, 3, 5) <= d <= dt.date(2026, 3, 20): m *= 2.0
    if d.weekday() >= 4: m *= 1.3
    return m


def main():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if os.path.exists(DB):
        os.remove(DB)
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)
    con.executemany("INSERT INTO vendors VALUES (?,?,?,?)", VENDORS)
    tx, inv = [], []

    def add(d, typ, cat, vendor, desc, amt):
        tx.append((d.isoformat(), typ, cat, vendor, desc, round(amt, 2)))

    d, weekly_sales = START, 0.0
    while d <= END:
        sales = random.gauss(4200, 450) * season(d)
        add(d, "income", "Sales", None, "Daily store sales", sales)
        weekly_sales += sales
        if d.weekday() == 0:  # Monday: pay suppliers ~56% of last week's sales
            ratio = 0.56 * (1.12 if d.month == 2 and d.year == 2026 else 1.0)
            split = {"Golden Grain Imports": .25, "Kerman Nuts Ltd.": .2, "Zarrin Saffron Co.": .1,
                     "Pacific Dairy": .25, "Fraser Valley Produce": .2}
            for v, share in split.items():
                amt = weekly_sales * ratio * share
                no = f"{v[:3].upper()}-{d.strftime('%y%m%d')}"
                add(d, "expense", "Suppliers", v, f"Invoice {no}", amt)
                inv.append((no, v, (d - dt.timedelta(days=7)).isoformat(), d.isoformat(), round(amt, 2), 0.0, round(amt, 2), "paid"))
            weekly_sales = 0.0
        if d.day == 1:
            add(d, "expense", "Rent", "Kingsway Properties", "Monthly rent", 12600)
            add(d, "expense", "Insurance", "Coastal Insurance", "Monthly premium", 840)
            add(d, "expense", "Software", "SquarePOS", "POS subscription", 223.88)
            add(d, "expense", "Software", "QuickLedger", "Accounting software", 100.80)
            if d >= dt.date(2026, 5, 1):
                add(d, "expense", "Software", "CloudBackup Pro", "Backup subscription", 145.60)
            add(d, "expense", "Marketing", "Local Ads Media", "Local ads", random.choice([600, 800, 1200]))
        if d.day == 15:
            winter = d.month in (11, 12, 1, 2)
            add(d, "expense", "Utilities", "BC Hydro", "Electricity", random.gauss(2300 if winter else 1700, 120))
            add(d, "expense", "Utilities", "FortisBC Gas", "Gas", random.gauss(900 if winter else 350, 60))
            add(d, "expense", "Utilities", "Telus Business", "Internet & phone", 212.80)
            add(d, "expense", "Services", "SparkleClean Services", "Monthly cleaning", 1344)
        if d.weekday() == 4 and (d - START).days // 7 % 2 == 0:  # every 2nd Friday
            add(d, "expense", "Payroll", None, "Staff payroll", random.gauss(17500, 400))
        if d in (dt.date(2026, 1, 22), dt.date(2026, 7, 9)):
            add(d, "expense", "Repairs", "CoolTech Refrigeration", "Walk-in cooler repair", 2150 if d.month == 1 else 3380)
        d += dt.timedelta(days=1)

    con.executemany("INSERT INTO transactions (date,type,category,vendor,description,amount) VALUES (?,?,?,?,?,?)", tx)
    con.executemany("INSERT INTO invoices VALUES (?,?,?,?,?,?,?,?)", inv)
    con.commit(); con.close()
    print(f"Created {DB}: {len(tx):,} transactions, {len(inv)} past invoices")


if __name__ == "__main__":
    main()
