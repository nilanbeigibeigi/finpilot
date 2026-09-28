"""Offline tests (no Ollama): fake LLM responses drive the real modules."""
import json, os, shutil, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import pytest


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    path = tmp_path / "f.db"
    monkeypatch.setenv("FINPILOT_DB", str(path))
    import importlib, db, seed_db
    importlib.reload(seed_db); seed_db.main()
    importlib.reload(db)
    for m in ("invoices", "ask", "forecast"):
        if m in sys.modules:
            importlib.reload(sys.modules[m])
    yield


def truth():
    return json.load(open(os.path.join(ROOT, "invoices", "ground_truth.json")))


def fake_extract(f):
    import invoices, re
    t = truth()[f]
    txt = invoices.pdf_text(os.path.join(ROOT, "invoices", f))
    amts = [float(x.replace(",", "")) for x in re.findall(r"\$([\d,]+\.\d\d)", txt)]
    items = [{"amount": a} for a in amts[1:len(amts) - 3:2]]
    return lambda s, u, json_mode=False: json.dumps({**t, "line_items": items})


def test_each_planted_invoice_problem_is_caught():
    import invoices
    for f, t in truth().items():
        r = invoices.process("ignored", chat=fake_extract(f))
        assert r["all_ok"] == (t["planted_issue"] is None), f


def test_approve_then_duplicate():
    import invoices
    r = invoices.process("x", chat=fake_extract("01_kerman_nuts.pdf"))
    invoices.approve(r["invoice"])
    again = invoices.process("x", chat=fake_extract("01_kerman_nuts.pdf"))
    assert not next(c for c in again["checks"] if c["check"] == "Not a duplicate")["ok"]


def test_sql_guard_blocks_writes():
    import ask
    for bad in ["DELETE FROM transactions", "SELECT 1; DROP TABLE vendors", "UPDATE invoices SET total=0"]:
        with pytest.raises(ValueError):
            ask.check_sql(bad)
    assert ask.check_sql("SELECT 1;") == "SELECT 1"


def test_ask_self_corrects_after_bad_sql():
    import ask
    replies = iter(['{"sql": "SELECT nope FROM transactions"}',
                    '{"sql": "SELECT ROUND(SUM(amount),2) AS total FROM transactions WHERE type=\'income\'"}',
                    "Total revenue was $1,857,992."])
    r = ask.ask("total revenue?", chat=lambda s, u, json_mode=False: next(replies))
    assert r["attempts"] == 2 and r["result"].iloc[0, 0] > 1_000_000


def test_forecast_and_what_if():
    import forecast
    base = forecast.forecast()
    worse = forecast.forecast(sales_change_pct=-20)
    assert len(base) == 3 and list(base.month) == ["2026-10", "2026-11", "2026-12"]
    assert worse.ending_cash.iloc[-1] < base.ending_cash.iloc[-1]


def test_monthly_has_losses_in_feb_and_june():
    import db
    m = db.monthly()
    assert set(m[m.profit < 0].month) == {"2026-02", "2026-06"}
