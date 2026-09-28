"""InvoiceIQ module: PDF -> text -> AI extraction (JSON) -> rule-based checks -> human approval.

The AI only READS the invoice. All checks are plain Python rules, so they are predictable and auditable.
"""
import datetime as dt
import io
import json

import db
import llm

SYSTEM = """You extract data from supplier invoices. Return ONLY JSON with exactly these keys:
{"vendor": str, "invoice_no": str, "invoice_date": "YYYY-MM-DD", "due_date": "YYYY-MM-DD",
 "line_items": [{"description": str, "quantity": number, "unit_price": number, "amount": number}],
 "subtotal": number, "tax": number, "total": number}
Copy numbers exactly as printed on the invoice (no $ signs or commas). Do NOT fix or recalculate anything —
if the invoice's math is wrong, keep the wrong numbers. Use null if a field is missing."""


def pdf_text(file) -> str:
    from pypdf import PdfReader
    data = file.read() if hasattr(file, "read") else open(file, "rb").read()
    return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)


def extract(text: str, chat=llm.chat) -> dict:
    return llm.parse_json(chat(SYSTEM, f"INVOICE TEXT:\n{text}", json_mode=True))


def _num(x):
    try:
        return round(float(str(x).replace("$", "").replace(",", "")), 2)
    except (TypeError, ValueError):
        return None


def validate(inv: dict) -> list[dict]:
    """Returns a list of checks: {check, ok, detail}."""
    checks = []
    add = lambda name, ok, detail: checks.append({"check": name, "ok": bool(ok), "detail": detail})
    sub, tax, tot = _num(inv.get("subtotal")), _num(inv.get("tax")), _num(inv.get("total"))
    items = inv.get("line_items") or []
    item_sum = round(sum(_num(i.get("amount")) or 0 for i in items), 2)

    missing = [k for k in ("vendor", "invoice_no", "invoice_date", "total") if not inv.get(k)]
    add("Required fields present", not missing, "All present" if not missing else f"Missing: {', '.join(missing)}")

    if items and sub is not None:
        add("Line items add up to subtotal", abs(item_sum - sub) <= 0.02,
            f"Items sum to ${item_sum:,.2f}; subtotal says ${sub:,.2f}")
    if None not in (sub, tax, tot):
        add("Subtotal + tax = total", abs(sub + tax - tot) <= 0.02,
            f"${sub:,.2f} + ${tax:,.2f} = ${sub + tax:,.2f}; total says ${tot:,.2f}")

    v = db.query("SELECT * FROM vendors WHERE lower(name) = lower(?)", (inv.get("vendor") or "",))
    add("Known vendor", len(v) == 1, "Approved vendor" if len(v) else
        f"'{inv.get('vendor')}' is not on the approved vendor list — possible fraud or new supplier")
    if len(v) and sub is not None and tax is not None:
        rate = float(v.expected_tax_rate[0])
        expected = round(sub * rate, 2)
        add("Tax matches vendor's expected rate", abs(expected - tax) <= 0.05,
            f"Expected {rate:.0%} = ${expected:,.2f}; invoice charges ${tax:,.2f}")

    dup = db.query("SELECT status, invoice_date FROM invoices WHERE lower(vendor)=lower(?) AND invoice_no=?",
                   (inv.get("vendor") or "", inv.get("invoice_no") or ""))
    add("Not a duplicate", dup.empty, "New invoice number" if dup.empty else
        f"Invoice {inv.get('invoice_no')} already recorded ({dup.status[0]}, dated {dup.invoice_date[0]})")

    try:
        d0, d1 = dt.date.fromisoformat(inv["invoice_date"]), dt.date.fromisoformat(inv["due_date"])
        add("Due date after invoice date", d1 >= d0, f"{(d1 - d0).days} days to pay")
    except (KeyError, TypeError, ValueError):
        add("Due date after invoice date", False, "Dates missing or unreadable")
    return checks


def process(text: str, chat=llm.chat) -> dict:
    inv = extract(text, chat)
    checks = validate(inv)
    return {"invoice": inv, "checks": checks, "all_ok": all(c["ok"] for c in checks)}


def approve(inv: dict):
    db.insert_invoice({**inv, **{k: _num(inv[k]) for k in ("subtotal", "tax", "total")}})


if __name__ == "__main__":
    import sys
    r = process(pdf_text(sys.argv[1]))
    print(json.dumps(r["invoice"], indent=2))
    for c in r["checks"]:
        print(("✅" if c["ok"] else "❌"), c["check"], "—", c["detail"])
