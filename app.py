"""FinPilot — AI finance operations.   Run:  python -m streamlit run app.py"""
import os

import streamlit as st

import ask
import db
import forecast
import invoices

st.set_page_config(page_title="FinPilot", page_icon="💰", layout="wide")
st.title("💰 FinPilot")
st.caption("AI finance operations for Saffron Market — dashboard, ask-your-data, invoice checks, and cash-flow forecasting. "
           "Runs locally; the AI reads and explains, rules and people make the decisions.")

if not os.path.exists(db.DB):
    st.error("No database yet. Run `python seed_db.py` in the terminal, then refresh.")
    st.stop()

tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "💬 Ask your finances", "🧾 Invoices", "📈 Cash-flow forecast"])

AI_ERROR = ("The AI model failed: {e}\n\nIs Ollama running, and did you pull the model? "
            "(`ollama pull qwen2.5:7b`, or set CHAT_MODEL=llama3.2)")

# ------------------------------------------------------------------ 1. dashboard
with tab1:
    m = db.monthly()
    rev, exp = m.revenue.sum(), m.expenses.sum()
    c = st.columns(4)
    c[0].metric("Revenue (12 mo)", f"${rev:,.0f}")
    c[1].metric("Expenses (12 mo)", f"${exp:,.0f}")
    c[2].metric("Profit (12 mo)", f"${rev - exp:,.0f}")
    c[3].metric("Profit margin", f"{100 * (rev - exp) / rev:.1f}%")

    st.subheader("Revenue vs expenses by month")
    st.bar_chart(m.set_index("month")[["revenue", "expenses"]], stack=False)
    losses = m[m.profit < 0]
    if len(losses):
        st.warning("Months that lost money: " + ", ".join(f"**{r.month}** (${r.profit:,.0f})" for r in losses.itertuples()))

    a, b = st.columns(2)
    with a:
        st.subheader("Expenses by category")
        cat = db.query("SELECT category, ROUND(SUM(amount)) AS total FROM transactions WHERE type='expense' "
                       "GROUP BY category ORDER BY total DESC")
        st.bar_chart(cat.set_index("category"), horizontal=True)
    with b:
        st.subheader("Recurring software subscriptions")
        subs = db.query("SELECT vendor, MIN(date) AS since, ROUND(AVG(amount),2) AS monthly FROM transactions "
                        "WHERE category='Software' GROUP BY vendor ORDER BY since")
        st.dataframe(subs, hide_index=True, width="stretch")
        st.caption("Tip: check any subscription that started recently — is it still needed?")
    st.subheader("Monthly table")
    st.dataframe(m, hide_index=True, width="stretch")

# ------------------------------------------------------------------ 2. ask
with tab2:
    st.caption("Ask in plain English. The AI writes a SQL query (shown below), it runs read-only, then the AI explains the result.")
    examples = ["In which months did we lose money?", "How much did we pay Kerman Nuts Ltd. in total?",
                "Which expense category was the biggest?", "When did we start paying for CloudBackup Pro?"]
    cols = st.columns(len(examples))
    picked = next((q for col, q in zip(cols, examples) if col.button(q, width="stretch")), None)
    q = st.text_input("Your question", value=picked or "", placeholder="e.g. What was total revenue in March 2026?")
    if q:
        try:
            with st.spinner("Writing and running the query…"):
                r = ask.ask(q)
            st.success(r["answer"])
            with st.expander("🔍 SQL the AI wrote" + (" (fixed itself after an error)" if r.get("attempts") == 2 else "")):
                st.code(r["sql"] or "", language="sql")
            if r["result"] is not None:
                st.dataframe(r["result"], hide_index=True, width="stretch")
        except Exception as e:
            st.error(AI_ERROR.format(e=e))

# ------------------------------------------------------------------ 3. invoices
with tab3:
    st.caption("Upload an invoice PDF. The AI reads it; rule-based checks verify it; a person approves or rejects.")
    samples = sorted(f for f in os.listdir(os.path.join(db.HERE, "invoices")) if f.endswith(".pdf"))
    left, right = st.columns([1, 2])
    with left:
        up = st.file_uploader("Upload invoice PDF", type="pdf")
        sample = st.selectbox("…or try a sample", ["—"] + samples)
        go = st.button("🔎 Read & check invoice", type="primary", width="stretch")
    if go and (up or sample != "—"):
        try:
            with st.spinner("Reading the invoice…"):
                text = invoices.pdf_text(up if up else os.path.join(db.HERE, "invoices", sample))
                st.session_state.inv = invoices.process(text)
        except Exception as e:
            st.error(AI_ERROR.format(e=e))
    r = st.session_state.get("inv")
    if r:
        with right:
            inv = r["invoice"]
            st.subheader(f"{inv.get('vendor')} · #{inv.get('invoice_no')}")
            k = st.columns(3)
            k[0].metric("Subtotal", f"${invoices._num(inv.get('subtotal')) or 0:,.2f}")
            k[1].metric("Tax", f"${invoices._num(inv.get('tax')) or 0:,.2f}")
            k[2].metric("Total", f"${invoices._num(inv.get('total')) or 0:,.2f}")
            if inv.get("line_items"):
                st.dataframe(inv["line_items"], width="stretch")
            for ch in r["checks"]:
                st.markdown(f"{'✅' if ch['ok'] else '❌'} **{ch['check']}** — {ch['detail']}")
            if r["all_ok"]:
                st.success("All checks passed.")
            else:
                st.error(f"{sum(not c['ok'] for c in r['checks'])} problem(s) found — review before paying.")
            a, b = st.columns(2)
            if a.button("✅ Approve for payment", width="stretch"):
                try:
                    invoices.approve(inv); st.toast("Invoice approved and recorded."); st.session_state.inv = None; st.rerun()
                except Exception as e:
                    st.error(f"Could not record it: {e}")
            if b.button("❌ Reject", width="stretch"):
                st.session_state.inv = None; st.toast("Invoice rejected."); st.rerun()

# ------------------------------------------------------------------ 4. forecast
with tab4:
    st.caption("Next 3 months. Revenue follows last year's seasonality (Yalda, Nowruz); costs follow the last 3 months.")
    s = st.columns(5)
    start = s[0].number_input("Cash today ($)", 0, 1_000_000, 85_000, step=5_000)
    sales = s[1].slider("Sales change %", -40, 40, 0)
    supp = s[2].slider("Supplier price change %", -20, 30, 0)
    new_cost = s[3].number_input("New monthly cost ($)", 0, 100_000, 0, step=500)
    one_off = s[4].number_input("One-time cost ($)", 0, 500_000, 0, step=1_000)
    fc = forecast.forecast(start, sales, supp, new_cost, one_off)
    floor = forecast.safety_floor()
    st.line_chart(fc.set_index("month")[["ending_cash"]])
    st.dataframe(fc, hide_index=True, width="stretch")
    low = fc[fc.ending_cash < floor]
    if len(low):
        st.error(f"⚠️ Cash drops below the safety floor (${floor:,.0f} = one month of fixed costs) in: "
                 + ", ".join(low.month))
    else:
        st.success(f"Cash stays above the safety floor (${floor:,.0f} = one month of fixed costs).")
    if st.button("🧠 Explain this forecast"):
        try:
            with st.spinner("Thinking…"):
                st.info(forecast.explain(fc, {"sales_change_pct": sales, "supplier_change_pct": supp,
                                              "new_monthly_cost": new_cost, "one_time_cost": one_off, "start_cash": start}))
        except Exception as e:
            st.error(AI_ERROR.format(e=e))
