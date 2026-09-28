"""Generate the sample invoice PDFs + ground truth (needs: pip install reportlab). Already run — PDFs are included."""
import json
import os

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "invoices")

# (file, vendor, address, invoice_no, date, due, items[(desc, qty, unit)], tax_rate, overrides, planted_issue)
INVOICES = [
    ("01_kerman_nuts.pdf", "Kerman Nuts Ltd.", "88 Main St, Vancouver BC", "KN-4471", "2026-09-14", "2026-10-14",
     [("Pistachios roasted 1lb case (24)", 6, 212.40), ("Mixed ajil 1lb case (24)", 4, 186.00)], 0.0, {}, None),
    ("02_pacific_dairy.pdf", "Pacific Dairy", "2100 Dairy Rd, Surrey BC", "PD-99812", "2026-09-15", "2026-09-29",
     [("Feta Persian style 400g (12)", 10, 58.80), ("Doogh 1.5L (6)", 15, 17.94), ("Yogurt mast 750g (12)", 8, 41.88)], 0.0, {}, None),
    ("03_sparkleclean.pdf", "SparkleClean Services", "45 Clean Ave, Burnaby BC", "SC-2026-09", "2026-09-30", "2026-10-30",
     [("Monthly store cleaning - September", 1, 1200.00)], 0.12, {}, None),
    ("04_cooltech.pdf", "CoolTech Refrigeration", "9 Frost Way, Richmond BC", "CT-1188", "2026-09-18", "2026-10-03",
     [("Service call - deli fridge", 1, 180.00), ("Compressor relay part", 2, 64.50), ("Labour (hours)", 3, 95.00)], 0.12, {}, None),
    ("05_golden_grain.pdf", "Golden Grain Imports", "300 Rice Blvd, Delta BC", "GG-7730", "2026-09-16", "2026-10-16",
     [("Basmati rice 10lb (4)", 20, 79.96), ("Red lentils 2lb (12)", 5, 52.80)], 0.0, {"total": 1897.20}, "total_mismatch"),
    ("06_fraser_valley.pdf", "Fraser Valley Produce", "12 Farm Rd, Abbotsford BC", "FVP-5521", "2026-09-17", "2026-09-24",
     [("Pomegranates case (40)", 6, 72.00), ("Persian cucumbers 20lb", 8, 38.50), ("Fresh herbs bunch (50)", 3, 61.00)], 0.0, {"subtotal": 925.00, "total": 925.00}, "line_items_mismatch"),
    ("07_local_ads.pdf", "Local Ads Media", "77 Media Row, Vancouver BC", "LAM-340", "2026-09-20", "2026-10-20",
     [("Community newspaper ad - Mehregan", 1, 900.00)], 0.15, {}, "wrong_tax_rate"),
    ("08_zarrin_duplicate.pdf", "Zarrin Saffron Co.", "5 Saffron Lane, Vancouver BC", "ZAR-260907", "2026-09-21", "2026-10-06",
     [("Saffron 2g tins (50)", 2, 412.00)], 0.0, {}, "duplicate_invoice"),
    ("09_unknown_vendor.pdf", "Premium Pistachio Traders", "PO Box 4412, Online", "PPT-0001", "2026-09-22", "2026-09-23",
     [("Pistachio consulting fee", 1, 2400.00)], 0.0, {}, "unknown_vendor"),
]


def build():
    os.makedirs(OUT, exist_ok=True)
    truth = {}
    for f, vendor, addr, no, date, due, items, rate, over, issue in INVOICES:
        lines = [(d, q, u, round(q * u, 2)) for d, q, u in items]
        subtotal = over.get("subtotal", round(sum(l[3] for l in lines), 2))
        tax = round(round(sum(l[3] for l in lines), 2) * rate, 2)
        total = over.get("total", round(subtotal + tax, 2))
        c = canvas.Canvas(os.path.join(OUT, f), pagesize=letter)
        c.setFont("Helvetica-Bold", 18); c.drawString(50, 740, vendor)
        c.setFont("Helvetica", 10); c.drawString(50, 724, addr)
        c.setFont("Helvetica-Bold", 14); c.drawString(400, 740, "INVOICE")
        c.setFont("Helvetica", 10)
        c.drawString(400, 724, f"Invoice #: {no}"); c.drawString(400, 710, f"Date: {date}"); c.drawString(400, 696, f"Due: {due}")
        c.drawString(50, 680, "Bill to: Saffron Market, 1500 Kingsway, Vancouver BC")
        y = 640
        c.setFont("Helvetica-Bold", 10)
        for x, h in ((50, "Description"), (330, "Qty"), (390, "Unit price"), (480, "Amount")): c.drawString(x, y, h)
        c.setFont("Helvetica", 10)
        for d, q, u, a in lines:
            y -= 18
            c.drawString(50, y, d); c.drawString(330, y, str(q)); c.drawString(390, y, f"${u:,.2f}"); c.drawString(480, y, f"${a:,.2f}")
        y -= 36
        c.drawString(390, y, "Subtotal:"); c.drawString(480, y, f"${subtotal:,.2f}")
        c.drawString(390, y - 16, f"Tax ({rate*100:.0f}%):" if rate else "Tax:"); c.drawString(480, y - 16, f"${tax:,.2f}")
        c.setFont("Helvetica-Bold", 11); c.drawString(390, y - 34, "TOTAL:"); c.drawString(480, y - 34, f"${total:,.2f}")
        c.setFont("Helvetica", 9); c.drawString(50, 80, "Thank you for your business.")
        c.save()
        truth[f] = {"vendor": vendor, "invoice_no": no, "invoice_date": date, "due_date": due,
                    "subtotal": subtotal, "tax": tax, "total": total, "planted_issue": issue}
    json.dump(truth, open(os.path.join(OUT, "ground_truth.json"), "w"), indent=2)
    print(f"Wrote {len(truth)} invoices to {OUT}")


if __name__ == "__main__":
    build()
