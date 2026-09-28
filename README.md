# 💰 FinPilot — AI finance operations for a small business

One system that combines four finance jobs a small business actually has, built for a fictional Persian grocery store, **Saffron Market** (12 months of synthetic data):

| Module | What it does | AI's role |
|---|---|---|
| 📊 **Dashboard** | Revenue, expenses, profit, margin by month; loss months; subscriptions | None — plain analytics |
| 💬 **Ask your finances** | "In which months did we lose money?" | Writes SQL, then explains the result |
| 🧾 **Invoices** | Upload a PDF → extract → 7 checks → approve/reject | Reads the invoice only |
| 📈 **Cash-flow forecast** | 3 months ahead + what-if sliders + safety floor | Explains risks in plain English |

Runs **100% locally** with Ollama. No financial data leaves the computer.

## Design principle: the AI reads and explains — rules and people decide
Finance can't tolerate a model that "sounds right". So:
- **Invoice checks are Python rules, not AI opinions.** The AI only extracts fields; the math, tax, duplicate, vendor and date checks are deterministic and auditable.
- **The AI is told not to fix invoice math** — it must copy numbers exactly, or it would hide the errors we're trying to catch.
- **Text-to-SQL is sandboxed:** only a single `SELECT` is allowed, write keywords are blocked, and the database is opened read-only. The SQL is always shown to the user.
- **Self-correction:** if the AI's SQL fails, the error goes back to the AI once so it can fix its own query.
- **Forecasts are math, not AI.** Seasonal-naive revenue (captures Yalda and Nowruz) + cost ratios from the last 3 months. The AI only explains the numbers.
- **A person approves every invoice** before it's recorded.

## What the data reveals (planted, so the tools can be verified)
- 📉 **February 2026 lost money** — supplier costs rose ~12% (nut & saffron price increase).
- 📉 **June 2026 lost money** — three payroll runs fell in one month.
- 🔍 **A forgotten subscription** ("CloudBackup Pro") started in May 2026.
- 🧾 **5 of the 9 sample invoices have problems:** a wrong total, line items that don't add up, a wrong tax rate, a duplicate invoice number, and an unknown vendor.

## Evaluation
```bash
python eval.py
```
| Test | What it measures |
|---|---|
| Invoice extraction | Vendor, invoice #, date and total read correctly (9 invoices) |
| Problems caught | Planted-problem invoices flagged (target 5/5) |
| Clean invoices passed | No false alarms (target 4/4) |
| SQL answer accuracy | AI's query returns the same answer as a hand-written reference query (10 questions) |

The rule checks alone catch **5/5 problems with 0 false alarms** (verified by the offline tests). `eval.py` measures the full pipeline with the real model.

## Setup
1. Install [Ollama](https://ollama.com) and pull a model:
   ```bash
   ollama pull qwen2.5:7b
   ```
   (Smaller/faster: `ollama pull llama3.2` and set `CHAT_MODEL=llama3.2`.)
2. Install, create the data, test:
   ```bash
   pip install -r requirements.txt
   python seed_db.py
   pytest -q
   ```
3. Run:
   ```bash
   python -m streamlit run app.py
   ```

## Files
| File | Purpose |
|---|---|
| `app.py` | Streamlit app (4 tabs) |
| `db.py` | Read-only queries + the one guarded write (approved invoices) |
| `ask.py` | Text-to-SQL with safety checks and self-correction |
| `invoices.py` | PDF reading, AI extraction, 7 rule-based checks |
| `forecast.py` | Cash-flow forecast, what-ifs, safety floor |
| `llm.py` | Small Ollama client |
| `seed_db.py` | Generates the 12-month dataset |
| `invoices/` | 9 sample invoice PDFs + `ground_truth.json` |
| `eval.py` | End-to-end evaluation |
| `tests/` | Offline tests with a fake LLM (no Ollama needed) |

Stack: Python · SQLite · pandas · Ollama (Qwen 2.5 / Llama 3.2) · pypdf · Streamlit · pytest
