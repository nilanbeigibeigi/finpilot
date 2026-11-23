"""Ask-your-finances module: question -> AI writes SQL -> safety check -> run read-only -> AI explains.

If the SQL fails, the error is sent back to the AI once so it can fix its own query.
"""
import json
import re

import db
import llm

SQL_SYSTEM = """You write SQLite queries for a grocery store's finance database.
{schema}

Notes:
- transactions.amount is always positive; use type = 'income' or 'expense'.
- Sales are rows with category = 'Sales'. Profit = income - expenses.
- Dates are TEXT 'YYYY-MM-DD'. Month: substr(date,1,7). Data covers 2025-10-01 to 2026-09-30.
- Round money to 2 decimals.
- Monthly profit pattern (use it for any profit / loss / 'lose money' question):
  SELECT substr(date,1,7) AS month, ROUND(SUM(CASE WHEN type='income' THEN amount ELSE -amount END),2) AS profit
  FROM transactions GROUP BY month
- 'Lost money' means that month's profit < 0. Include the profit column so the answer can show the amounts.
- Only use category and vendor values from the exact lists above. A product or service name (e.g. a subscription or a repair company) is usually a vendor; match with vendor LIKE '%word%' if unsure.
- 'The year' or 'the whole year' means all data (2025-10-01 to 2026-09-30), with no date filter.
- Keep queries simple: one GROUP BY, no date filters unless the question names a period.
Return ONLY JSON: {{"sql": "<one SELECT query>"}}"""

ANSWER_SYSTEM = """You are a finance assistant. Answer the question in 1-3 sentences using ONLY the query result.
Use $ and thousands separators. If the result is empty, say no matching data was found. Never invent numbers."""

FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|alter|create|attach|detach|pragma|replace|vacuum)\b", re.I)


def check_sql(sql: str) -> str:
    sql = sql.strip().rstrip(";").strip()
    if not re.match(r"^(select|with)\b", sql, re.I):
        raise ValueError("Only SELECT queries are allowed.")
    if ";" in sql or FORBIDDEN.search(sql):
        raise ValueError("Query contains a forbidden statement.")
    return sql


def write_sql(question: str, chat=llm.chat, error: str | None = None, bad_sql: str | None = None) -> str:
    user = f"QUESTION: {question}"
    if error:
        user += f"\n\nYour previous query:\n{bad_sql}\nfailed with: {error}\nFix it."
    return llm.parse_json(chat(SQL_SYSTEM.format(schema=db.schema_text()), user, json_mode=True))["sql"]


def ask(question: str, chat=llm.chat) -> dict:
    sql, error = None, None
    for attempt in range(2):  # 1 try + 1 self-correction
        try:
            sql = check_sql(write_sql(question, chat, error, sql))
            df = db.query(f"SELECT * FROM ({sql}) LIMIT 200")
            break
        except Exception as e:
            error = str(e)
    else:
        return {"question": question, "sql": sql, "result": None, "answer": f"I couldn't build a working query: {error}"}
    preview = df.head(30).to_dict(orient="records")
    answer = chat(ANSWER_SYSTEM, f"QUESTION: {question}\nSQL: {sql}\nRESULT: {json.dumps(preview, default=str)}")
    return {"question": question, "sql": sql, "result": df, "answer": answer, "attempts": attempt + 1}


if __name__ == "__main__":
    import sys
    r = ask(" ".join(sys.argv[1:]) or "What was total revenue in March 2026?")
    print(r["sql"], "\n", r["result"], "\n\n", r["answer"])
