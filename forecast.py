"""Cash-flow module: 3-month forecast + what-if scenarios. Pure math (explainable); AI only explains the result.

Method:
  revenue   = same month last year  × (1 + sales change %)          (seasonal naive — captures Yalda/Nowruz)
  suppliers = revenue × supplier cost ratio of the last 3 months
  fixed     = average of each other expense category over the last 3 months (+ any new monthly cost)
"""
import pandas as pd

import db
import llm


def forecast(start_cash: float = 85000, sales_change_pct: float = 0, supplier_change_pct: float = 0,
             new_monthly_cost: float = 0, one_time_cost: float = 0, months: int = 3) -> pd.DataFrame:
    tx = db.query("SELECT substr(date,1,7) AS month, type, category, amount FROM transactions")
    rev = tx[tx.type == "income"].groupby("month").amount.sum()
    exp = tx[tx.type == "expense"].pivot_table(index="month", columns="category", values="amount", aggfunc="sum").fillna(0)
    last3 = sorted(rev.index)[-3:]
    supplier_ratio = exp.loc[last3, "Suppliers"].sum() / rev.loc[last3].sum() * (1 + supplier_change_pct / 100)
    fixed = exp.drop(columns="Suppliers").loc[last3].mean().sum() + new_monthly_cost

    last = pd.Period(max(rev.index), "M")
    rows, cash = [], start_cash
    for i in range(1, months + 1):
        p = last + i
        base = rev.get(str(p - 12), rev.mean())
        r = base * (1 + sales_change_pct / 100)
        s = r * supplier_ratio
        f = fixed + (one_time_cost if i == 1 else 0)
        cash += r - s - f
        rows.append({"month": str(p), "revenue": r, "suppliers": s, "other_costs": f,
                     "net_cash_flow": r - s - f, "ending_cash": cash})
    return pd.DataFrame(rows).round(0)


def safety_floor() -> float:
    """One month of non-supplier costs = minimum cash the business should keep."""
    tx = db.query("SELECT substr(date,1,7) m, amount FROM transactions WHERE type='expense' AND category!='Suppliers'")
    return round(tx.groupby("m").amount.sum().tail(3).mean(), 0)


def explain(df: pd.DataFrame, scenario: dict, chat=llm.chat) -> str:
    system = ("You are a careful small-business finance advisor. In 3-4 short bullet points, explain this cash-flow "
              "forecast: the trend, the biggest risk, and one practical action. Use ONLY the numbers given.")
    return chat(system, f"Scenario: {scenario}\nSafety floor (1 month of fixed costs): ${safety_floor():,.0f}\n"
                        f"Forecast:\n{df.to_string(index=False)}")


if __name__ == "__main__":
    print(forecast())
    print("Safety floor:", safety_floor())
