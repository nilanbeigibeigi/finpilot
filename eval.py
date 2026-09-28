"""Evaluate FinPilot's two AI modules against known answers.

  1. Invoices: does the AI extract the right fields, and do the checks catch the 5 planted problems?
  2. Ask:      does the AI's SQL return the same answer as a hand-written reference query?

    python eval.py
"""
import json
import os
import time

import ask
import db
import invoices
import llm

HERE = os.path.dirname(os.path.abspath(__file__))


def _vals(df):
    out = set()
    for v in df.values.flatten():
        try:
            out.add(round(float(v), 0))
        except (TypeError, ValueError):
            out.add(str(v).strip().lower())
    return out


def eval_invoices():
    truth = json.load(open(os.path.join(HERE, "invoices", "ground_truth.json")))
    rows = []
    for f, t in truth.items():
        print(f"  invoice {f}")
        r = invoices.process(invoices.pdf_text(os.path.join(HERE, "invoices", f)))
        inv = r["invoice"]
        fields = ["vendor", "invoice_no", "invoice_date", "total"]
        extracted_ok = all(str(inv.get(k)).strip().lower() == str(t[k]).strip().lower() if k != "total"
                           else invoices._num(inv.get(k)) == t[k] for k in fields)
        flagged = not r["all_ok"]
        rows.append({"file": f, "issue": t["planted_issue"], "extracted_ok": extracted_ok,
                     "flagged": flagged, "correct": flagged == (t["planted_issue"] is not None)})
    return rows


def eval_sql():
    qs = json.load(open(os.path.join(HERE, "eval_questions.json")))
    rows = []
    for item in qs:
        print(f"  ask: {item['q']}")
        expected = _vals(db.query(item["sql"]))
        r = ask.ask(item["q"])
        got = _vals(r["result"]) if r["result"] is not None else set()
        rows.append({"q": item["q"], "correct": expected <= got, "sql": r["sql"], "answer": r["answer"]})
    return rows


def main():
    t0 = time.time()
    print("Invoices…"); inv = eval_invoices()
    print("Questions…"); sq = eval_sql()
    pct = lambda rows, k: round(100 * sum(r[k] for r in rows) / len(rows), 1)
    summary = {
        "model": llm.CHAT_MODEL,
        "invoice_extraction_accuracy": pct(inv, "extracted_ok"),
        "problem_invoices_caught": f"{sum(r['flagged'] for r in inv if r['issue'])}/{sum(1 for r in inv if r['issue'])}",
        "clean_invoices_passed": f"{sum(not r['flagged'] for r in inv if not r['issue'])}/{sum(1 for r in inv if not r['issue'])}",
        "sql_answer_accuracy": pct(sq, "correct"),
        "seconds": round(time.time() - t0, 1),
    }
    print("\n" + json.dumps(summary, indent=2))
    for r in inv:
        if not r["correct"] or not r["extracted_ok"]:
            print("  ⚠ invoice:", r["file"], "| extracted ok:", r["extracted_ok"], "| flagged:", r["flagged"])
    for r in sq:
        if not r["correct"]:
            print("  ⚠ question:", r["q"], "\n      SQL:", r["sql"])
    os.makedirs(os.path.join(HERE, "reports"), exist_ok=True)
    json.dump({"summary": summary, "invoices": inv, "questions": sq},
              open(os.path.join(HERE, "reports", f"eval_{llm.CHAT_MODEL.replace(':', '-')}.json"), "w"), indent=2)


if __name__ == "__main__":
    main()
