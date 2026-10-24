"""Churn call-list planner.

A small Streamlit app for the retention team: set how many customers you can
contact and what a contact costs, and see who to call first and how much of the
value at risk that protects.

Run locally from the repo folder:
    streamlit run app/streamlit_app.py
"""
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_predict

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "customer_churn.csv"
RANDOM_STATE = 42

st.set_page_config(page_title="Churn call-list planner", page_icon="📞", layout="wide")


# ---------------------------------------------------------------- data and model
@st.cache_data(show_spinner="Loading the Iranian Churn data...")
def load_customers() -> pd.DataFrame:
    """Same loading and cleaning as notebooks/01_explore.ipynb."""
    if RAW.exists():
        raw = pd.read_csv(RAW)
    else:  # first run (or on Streamlit Community Cloud): download from UCI
        from ucimlrepo import fetch_ucirepo

        uci = fetch_ucirepo(id=563)
        raw = pd.concat([uci.data.features, uci.data.targets], axis=1)
    df = raw.copy()
    df.columns = ["_".join(c.lower().split()) for c in df.columns]
    df.insert(0, "customer_id", [f"C{i:04d}" for i in range(1, len(df) + 1)])
    feature_cols = [c for c in df.columns if c != "customer_id"]
    return df.drop_duplicates(subset=feature_cols, keep="first").reset_index(drop=True)


@st.cache_data(show_spinner="Scoring every customer with the random forest (about 10 seconds)...")
def score_customers(customers: pd.DataFrame) -> pd.DataFrame:
    """Out-of-fold churn probabilities: each customer is scored by a model that never saw them."""
    features = [c for c in customers.columns if c not in ("customer_id", "churn")]
    forest = RandomForestClassifier(n_estimators=500, min_samples_leaf=3, n_jobs=-1, random_state=RANDOM_STATE)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    p = cross_val_predict(forest, customers[features], customers["churn"], cv=cv, method="predict_proba")[:, 1]
    return customers[["customer_id", "customer_value", "complains", "frequency_of_use", "churn"]].assign(p_churn=p)


customers = load_customers()
scored = score_customers(customers)


# ---------------------------------------------------------------- sidebar: the business settings
with st.sidebar:
    st.header("Your settings")
    capacity = st.slider("Customers the team can contact this quarter", 25, 1000, 300, step=25)
    contact_cost = st.number_input("Cost of one contact (R)", 10, 2000, 140, step=10,
                                   help="Agent time plus the retention offer.")
    value_if_saved = st.number_input("Value of a saved customer (R)", 100, 50000, 3000, step=100,
                                     help="About 12 months of revenue from an average customer.")
    save_rate = st.slider("Share of contacted churners who stay", 5, 80, 30, step=5, format="%d%%") / 100
    rank_by = st.radio("Rank customers by", ["Expected loss", "Churn probability"],
                       help="Expected loss = churn probability x customer value.")
    only_above = st.checkbox("Only contact customers above break-even", value=True,
                             help="Skip customers whose expected saving is smaller than the cost of contacting them.")

break_even = contact_cost / (save_rate * value_if_saved)


# ---------------------------------------------------------------- build the call list
df = scored.assign(expected_loss=scored.p_churn * scored.customer_value,
                   max_spend_rand=(scored.p_churn * save_rate * value_if_saved).round(0))
df["eligible"] = df.p_churn >= break_even if only_above else True
key = "expected_loss" if rank_by == "Expected loss" else "p_churn"
df = df.sort_values(["eligible", key], ascending=[False, False]).reset_index(drop=True)
df["rank"] = df.index + 1
df["tier"] = np.select(
    [~df.eligible, df["rank"] <= 50, df["rank"] <= capacity],
    ["No action", "1 Personal call", "2 Targeted offer"], default="3 Automated nudge")
contacted = df[df.eligible & (df["rank"] <= capacity)]

# Hindsight: these are historical customers, so we can check against who actually left
churners = df[df.churn == 1]
value_at_risk = churners.customer_value.sum()
value_protected = contacted.loc[contacted.churn == 1, "customer_value"].sum()
expected_net = (contacted.p_churn * save_rate * value_if_saved).sum() - len(contacted) * contact_cost


# ---------------------------------------------------------------- page
st.title("Churn call-list planner")
st.markdown(
    f"Which of **{len(df):,} customers** should the retention team contact first? "
    "Set your capacity and costs on the left; the list, the numbers and the chart update."
)

if only_above and len(contacted) < capacity:
    st.info(f"Only {len(contacted)} customers are above the break-even churn probability of "
            f"{break_even:.0%}, so the team has spare capacity. Contacting anyone else would cost more "
            "than it is expected to save.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Customers to contact", f"{len(contacted):,}", help=f"Break-even churn probability: {break_even:.1%}")
c2.metric("Churners reached", f"{int(contacted.churn.sum())} of {len(churners)}",
          f"{contacted.churn.sum() / len(churners):.0%} of all churners", delta_color="off", delta_arrow="off")
c3.metric("Value at risk protected", f"{value_protected / value_at_risk:.0%}",
          help="Share of the customer value of all churners that sits in the contact list.")
c4.metric("Expected net value", f"R{expected_net:,.0f}",
          help="Expected saves x value of a saved customer, minus the cost of every contact.")

st.subheader("How much value each ranking protects")
n = np.arange(len(df) + 1)


def captured(order: pd.Index) -> np.ndarray:
    lost = np.where(scored.loc[order, "churn"] == 1, scored.loc[order, "customer_value"], 0)
    return np.concatenate([[0], np.cumsum(lost)]) / value_at_risk


rng = np.random.default_rng(RANDOM_STATE)
curves = pd.DataFrame({
    "contacts": n,
    "Expected loss": captured(scored.assign(e=scored.p_churn * scored.customer_value).sort_values("e", ascending=False).index),
    "Churn probability": captured(scored.sort_values("p_churn", ascending=False).index),
    "Random calling": np.mean([captured(rng.permutation(scored.index)) for _ in range(50)], axis=0),
}).melt("contacts", var_name="Ranking", value_name="protected")
curves = curves[curves.contacts <= max(1000, capacity + 100)]

lines = alt.Chart(curves).mark_line().encode(
    x=alt.X("contacts:Q", title="Customers contacted, in ranked order"),
    y=alt.Y("protected:Q", title="Share of churn value protected", axis=alt.Axis(format="%")),
    color=alt.Color("Ranking:N", sort=["Expected loss", "Churn probability", "Random calling"],
                    scale=alt.Scale(range=["#2a78d6", "#eb6834", "#8a8984"]),
                    legend=alt.Legend(orient="bottom", direction="vertical", title=None)),
    tooltip=["Ranking", "contacts", alt.Tooltip("protected:Q", format=".0%")],
)
rule = alt.Chart(pd.DataFrame({"contacts": [capacity]})).mark_rule(strokeDash=[4, 4], color="#52514e").encode(x="contacts:Q")
st.altair_chart((lines + rule).properties(height=320), width="stretch")
st.caption("The dashed line is your capacity. The higher a curve is at that line, the more value that ranking protects.")

st.subheader("The call list")
tiers = df.assign(pct=df.p_churn * 100).groupby("tier").agg(customers=("customer_id", "size"), mean_churn_probability=("pct", "mean"),
                               max_spend_median=("max_spend_rand", "median")).rename_axis("Action")
st.dataframe(tiers, column_config={
    "mean_churn_probability": st.column_config.NumberColumn("Mean churn probability", format="%.0f%%"),
    "max_spend_median": st.column_config.NumberColumn("Median spending ceiling (R)", format="R%d"),
    "customers": "Customers"}, width="stretch")

show = contacted.assign(p_churn=(contacted.p_churn * 100).round(0))[["rank", "customer_id", "p_churn", "customer_value", "expected_loss", "max_spend_rand", "tier",
                  "complains", "frequency_of_use"]]
st.dataframe(show, hide_index=True, width="stretch", height=420, column_config={
    "rank": "Rank", "customer_id": "Customer",
    "p_churn": st.column_config.ProgressColumn("Churn probability", format="%d%%", min_value=0, max_value=100),
    "customer_value": st.column_config.NumberColumn("Customer value", format="%.0f"),
    "expected_loss": st.column_config.NumberColumn("Expected loss", format="%.0f"),
    "max_spend_rand": st.column_config.NumberColumn("Spend up to", format="R%d",
                                                    help="Most worth spending to keep this customer."),
    "tier": "Action", "complains": st.column_config.CheckboxColumn("Complained"),
    "frequency_of_use": st.column_config.NumberColumn("Calls (9 months)", format="%d"),
})
st.download_button("Download the call list (CSV)", show.to_csv(index=False).encode(), "call_list.csv", "text/csv")

with st.expander("How this works"):
    st.markdown(f"""
- **Data:** the [Iranian Churn dataset](https://archive.ics.uci.edu/dataset/563/iranian+churn+dataset) (UCI id 563),
  {len(df):,} customers after removing duplicate records, framed for a South African mobile operator.
- **Model:** the random forest from `notebooks/02_model.ipynb`. Every customer's churn probability comes from
  **5-fold out-of-fold scoring**: the model that scores a customer was trained without them, so the list is an honest
  preview of how the model would do on customers it has not seen.
- **Break-even:** contacting a customer is worth it when churn probability x save rate x value of a saved customer
  is more than the cost of a contact. With your settings that is a churn probability of **{break_even:.1%}**.
- **Expected loss** = churn probability x customer value (in the dataset's own value units). It ranks customers by how
  much they are likely to cost the business, not only by how likely they are to leave.
- **Hindsight numbers** ("churners reached", "value protected") use the real outcomes in the historical data. With
  live customers you would only have the probabilities.
- The rand amounts are working assumptions, not real operator figures. Change them to see how the plan responds.
""")
