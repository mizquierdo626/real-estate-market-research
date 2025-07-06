import pandas as pd
import streamlit as st

# Load master sheet
file_path = 'Top-Real-Estate-Markets-Raw-Data_GenAI.xlsx'
df = pd.read_excel(file_path, sheet_name='Master Score Sheet')

st.set_page_config(page_title="Golden Coast Capital Real Estate Market Scoring Tool", layout="wide")
st.title("\U0001F3E1 Golden Coast Capital Real Estate Market Scoring Tool")
st.subheader("\U0001F3AF Adjust Weights & Compare Markets")

# Sidebar adjustable financial inputs
st.sidebar.header("\U0001F4B8 Financial Assumptions")
interest_rate = st.sidebar.slider("Interest Rate (%)", 3.0, 10.0, 7.0) / 100
loan_term_years = st.sidebar.slider("Loan Term (Years)", 15, 30, 30)
down_payment_pct = st.sidebar.slider("Down Payment (%)", 0, 50, 20) / 100
str_expense_ratio = st.sidebar.slider("STR Expenses (% of Revenue)", 10, 60, 30) / 100
ltr_expense_ratio = st.sidebar.slider("LTR Expenses (% of Rent)", 10, 60, 40) / 100

# Capital filter
st.sidebar.header("\U0001F4B0 Capital Constraints")
max_investment = st.sidebar.number_input("Max Capital Available ($)", value=100000, step=10000)
include_renovation = st.sidebar.checkbox("Include $30K Renovation Buffer?", value=True)
buffer = 30000 if include_renovation else 0

# Mortgage & Cash Flow Calculation
price_col = 'Small Multi Median Sales Price 2025 YtD (2–4 Units)'
price = df[price_col]
loan_amount = price * (1 - down_payment_pct)
monthly_interest = interest_rate / 12
num_payments = loan_term_years * 12

# Monthly mortgage formula
monthly_mortgage = loan_amount * (
    (monthly_interest * (1 + monthly_interest) ** num_payments) /
    ((1 + monthly_interest) ** num_payments - 1)
)
df['Est_Mortgage'] = monthly_mortgage

# Cash Flow calculations
df['STR_Expenses'] = df['Annual Revenue'] * str_expense_ratio / 12
df['STR_CashFlow'] = (df['Annual Revenue'] / 12) - df['Est_Mortgage'] - df['STR_Expenses']
df['LTR_Expenses'] = df['2 Bed SFR Median Rent'] * ltr_expense_ratio
df['LTR_CashFlow'] = df['2 Bed SFR Median Rent'] - df['Est_Mortgage'] - df['LTR_Expenses']

df['STR_Positive_CF'] = (df['STR_CashFlow'] > 0).astype(int)
df['LTR_Positive_CF'] = (df['LTR_CashFlow'] > 0).astype(int)

# STR Yield
df['STR_Yield'] = df['Annual Revenue'] / price

# Capital requirement
df['Total_Cash_Required'] = (down_payment_pct + 0.04) * df[price_col] + buffer
df = df[df['Total_Cash_Required'] <= max_investment]

# Presets
presets = {
    "Balanced": {
        "STR Performance": 0.40,
        "LTR Safety Net": 0.25,
        "Entry & Value": 0.15,
        "Fundamentals": 0.20
    },
    "Cash Flow Heavy": {
        "STR Performance": 0.50,
        "LTR Safety Net": 0.30,
        "Entry & Value": 0.10,
        "Fundamentals": 0.10
    },
    "Appreciation First": {
        "STR Performance": 0.30,
        "LTR Safety Net": 0.20,
        "Entry & Value": 0.20,
        "Fundamentals": 0.30
    }
}

st.sidebar.header("⚖️ Weighting Method")
weight_mode = st.sidebar.radio("Choose how you'd like to set weights:", ["High-Level Themes", "Detailed Metrics"])

# Group definitions
groups = {
    "STR Performance": ["Market Score", "STR_Yield", "Occupancy", "Booking Demand Growth", "STR_Positive_CF"],
    "LTR Safety Net": ["Gross Yield (SFR)", "LTR_Positive_CF", "Rent-to-Price Ratio"],
    "Entry & Value": ["Small Multi Median Sales Price 2025 YtD (2–4 Units)", "Small Multi Discount Markets", "Home Value Growth (5 Years)"],
    "Fundamentals": ["Population Growth (5 years)", "Rent Growth (YoY)", "Vacancy Rate"]
}

metric_descriptions = {
    "Market Score": "Overall STR market performance score from AirDNA.",
    "STR_Yield": "STR Annual Revenue divided by property price.",
    "Occupancy": "Average annual occupancy rate for STR listings.",
    "Booking Demand Growth": "Growth in STR demand year over year.",
    "STR_Positive_CF": "Binary flag: does STR cash flow after expenses?",
    "Gross Yield (SFR)": "LTR gross income / property price.",
    "LTR_Positive_CF": "Binary flag: does LTR cash flow after expenses?",
    "Rent-to-Price Ratio": "Monthly rent divided by home price.",
    "Small Multi Median Sales Price 2025 YtD (2–4 Units)": "Median price for 2–4 unit properties.",
    "Small Multi Discount Markets": "Market discount compared to list price.",
    "Home Value Growth (5 Years)": "Appreciation over the past 5 years.",
    "Population Growth (5 years)": "Population change over the past 5 years.",
    "Rent Growth (YoY)": "Annual rent increase.",
    "Vacancy Rate": "% of unoccupied rental units (lower is better)."
}

# Weight setup
if weight_mode == "High-Level Themes":
    preset_choice = st.sidebar.selectbox("Apply Preset Template", list(presets.keys()))
    preset_weights = presets[preset_choice]

    group_weights = {
        group: st.sidebar.slider(group, 0.0, 1.0, preset_weights[group])
        for group in groups
    }
    metrics = {
        metric: group_weights[group] / len(groups[group])
        for group in groups for metric in groups[group]
    }

    st.sidebar.markdown("### Group Weight Breakdown")
    st.sidebar.bar_chart(pd.DataFrame(group_weights.values(), index=group_weights.keys(), columns=["Weight"]))
else:
    metrics = {}
    for group, metric_list in groups.items():
        st.sidebar.markdown(f"**{group}**")
        for metric in metric_list:
            help_text = metric_descriptions.get(metric, "")
            metrics[metric] = st.sidebar.slider(metric, 0.0, 1.0, 0.05, help=help_text)

# Normalize
score = 0
for col, weight in metrics.items():
    if col in df.columns:
        col_norm = (df[col] - df[col].min()) / (df[col].max() - df[col].min()) if df[col].max() != df[col].min() else 0
        df[col + "_norm"] = col_norm
        if "Price" in col or "Vacancy" in col:
            score += weight * (1 - df[col + "_norm"])
        else:
            score += weight * df[col + "_norm"]

df["Master Score"] = score
sorted_df = df.sort_values("Master Score", ascending=False)

# Results Table
top_n = st.selectbox("\U0001F539 Show Top N Markets", [5, 10, 15, 20], index=1)
st.dataframe(sorted_df[["Market Name", "State", "Master Score"] + list(metrics.keys())].head(top_n), use_container_width=True)

# Compare Section
st.markdown("---")
st.subheader("\U0001F4CA Compare Two Markets Side-by-Side")
market_list = sorted_df['Market Name'].unique().tolist()
col1, col2 = st.columns(2)

with col1:
    market_a = st.selectbox("Select Market A", market_list, index=0)
with col2:
    market_b = st.selectbox("Select Market B", market_list, index=1)

if market_a and market_b:
    a_data = sorted_df[sorted_df['Market Name'] == market_a].iloc[0]
    b_data = sorted_df[sorted_df['Market Name'] == market_b].iloc[0]

    compare_metrics = ["Master Score"] + list(metrics.keys())
    comp_table = pd.DataFrame({
        'Metric': compare_metrics,
        market_a: [a_data[m] for m in compare_metrics],
        market_b: [b_data[m] for m in compare_metrics],
    })
    st.dataframe(comp_table.set_index('Metric'), use_container_width=True)

    if st.button("\U0001F4CB Generate Investor Analysis"):
        summary = f"""\n🧠 **Investor Insight Analysis**\n\nAs a seasoned investor with decades of success, here's my high-level comparison between **{market_a}** and **{market_b}**:\n\n▶️ **{market_a}**:\n- Master Score: {a_data['Master Score']:.2f}\n- STR Yield: {a_data.get('STR_Yield', 'N/A'):.2%} | LTR Gross Yield: {a_data.get('Gross Yield (SFR)', 'N/A'):.2%}\n- Occupancy Rate: {a_data.get('Occupancy', 'N/A'):.1f}%\n- Median Price (2–4 Units): ${a_data.get(price_col, 0):,.0f}\n- STR Cash Flow: ${a_data.get('STR_CashFlow', 0):,.0f} | LTR Cash Flow: ${a_data.get('LTR_CashFlow', 0):,.0f}\n\n▶️ **{market_b}**:\n- Master Score: {b_data['Master Score']:.2f}\n- STR Yield: {b_data.get('STR_Yield', 'N/A'):.2%} | LTR Gross Yield: {b_data.get('Gross Yield (SFR)', 'N/A'):.2%}\n- Occupancy Rate: {b_data.get('Occupancy', 'N/A'):.1f}%\n- Median Price (2–4 Units): ${b_data.get(price_col, 0):,.0f}\n- STR Cash Flow: ${b_data.get('STR_CashFlow', 0):,.0f} | LTR Cash Flow: ${b_data.get('LTR_CashFlow', 0):,.0f}\n\n✅ **Recommendation**:\nIf you're seeking higher STR upside, go with **{market_a if a_data['STR_Yield'] > b_data['STR_Yield'] else market_b}**.\nIf long-term resilience and safety are top priority, **{market_a if a_data['LTR_CashFlow'] > b_data['LTR_CashFlow'] else market_b}** may win.\n"""
        st.markdown(summary)

# Download
st.download_button("\U0001F4C2 Download Full Scored Table", sorted_df.to_csv(index=False), file_name="top_markets_scored.csv")
