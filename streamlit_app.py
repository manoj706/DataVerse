import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# ==================================================
# PAGE CONFIG
# ==================================================
st.set_page_config(
    page_title="VelocityMart Operations Dashboard",
    page_icon="📦",
    layout="wide"
)

# ==================================================
# LOAD DATA (ONLY FILES YOU HAVE)
# ==================================================
@st.cache_data
def load_data():
    picker = pd.read_csv("data/cleaned_picker_movement.csv")
    orders = pd.read_csv("data/cleaned_order_transactions.csv")
    warehouse = pd.read_csv("data/cleaned_warehouse_constraints.csv")
    sku = pd.read_csv("data/cleaned_sku_master.csv")
    final_slotting = pd.read_csv("data/final_slotting_plan.csv")
    return picker, orders, warehouse, sku, final_slotting

picker_movement, orders, warehouse, sku_master, final_slotting = load_data()

orders["order_timestamp"] = pd.to_datetime(orders["order_timestamp"])
picker_movement["order_timestamp"] = pd.to_datetime(picker_movement["order_timestamp"]) 

# ==================================================
# GLOBAL AISLE TRAFFIC (USED EVERYWHERE)
# ==================================================
orders_with_slot = orders.merge(
    sku_master[["sku_id", "current_slot"]],
    on="sku_id",
    how="left"
)
orders_with_slot["aisle"] = orders_with_slot["current_slot"].str.extract(r"^([A-Z])")

aisle_traffic = (
    orders_with_slot
    .groupby("aisle")
    .size()
    .reset_index(name="visit_count")
)

total_traffic = aisle_traffic["visit_count"].sum()
if "B" in aisle_traffic["aisle"].values:
    b_traffic = aisle_traffic.loc[aisle_traffic["aisle"] == "B", "visit_count"].values[0]
    pct_b = (b_traffic / total_traffic) * 100
else:
    pct_b = 0.0

# ==================================================
# HEADER
# ==================================================
st.title("📦 VelocityMart Operations Dashboard")
st.subheader("Bangalore Dark Store – Real-Time Operations Intelligence")
st.markdown("---")

# ==================================================
# A. DATA FORENSICS & INTEGRITY
# ==================================================
st.header("🔍 Data Forensics & Integrity")
tab1, tab2, tab3 = st.tabs(["Decimal Drift", "Shortcut Paradox", "Ghost Inventory"])

# ---------- Decimal Drift (Option B+) ----------
with tab1:
    upper_domain_limit = 25
    lower_domain_limit = 0.01
    p99 = sku_master["weight_kg"].quantile(0.995)
    p001 = sku_master["weight_kg"].quantile(0.005)

    decimal_drift = sku_master[
        (sku_master["weight_kg"] > min(upper_domain_limit, p99)) |
        (sku_master["weight_kg"] < max(lower_domain_limit, p001))
    ]

    if len(decimal_drift) > 0:
        st.error(f"{len(decimal_drift)} SKUs flagged for potential decimal drift")
        st.dataframe(decimal_drift[["sku_id", "category", "weight_kg"]], use_container_width=True)
    else:
        st.success("No decimal drift detected under adaptive domain sanity rules")

# ---------- Shortcut Paradox ----------
with tab2:
    picker_stats = picker_movement.groupby("picker_id").agg(
        total_distance=("travel_distance_m", "sum"),
        total_orders=("order_id", "count")
    ).reset_index()

    picker_stats["orders_per_meter"] = picker_stats["total_orders"] / picker_stats["total_distance"]
    threshold = picker_stats["orders_per_meter"].quantile(0.95)
    shortcut_pickers = picker_stats[picker_stats["orders_per_meter"] > threshold]

    st.error(f"{len(shortcut_pickers)} suspicious picker(s) detected")
    st.dataframe(shortcut_pickers, use_container_width=True)

# ---------- Ghost Inventory ----------
with tab3:
    valid_bins = set(warehouse["slot_id"])
    ghost_bins = set(sku_master["current_slot"]) - valid_bins
    if ghost_bins:
        st.error("Ghost inventory detected")
        st.dataframe(sku_master[sku_master["current_slot"].isin(ghost_bins)])
    else:
        st.success("No ghost inventory detected")

# ==================================================
# B. DECISION-SUPPORT DASHBOARD (40 pts)
# ==================================================
st.markdown("---")
st.header("🚨 Critical Operational Visualizations")

# ---------- Heatmap @ 19:00 ----------
st.subheader("🔥 High-Collision Aisles — 19:00 Peak Hour")
orders_with_slot["hour"] = orders_with_slot["order_timestamp"].dt.hour
peak_orders = orders_with_slot[orders_with_slot["hour"] == 19]

aisle_counts = peak_orders.groupby("aisle").size().reset_index(name="orders")
fig, ax = plt.subplots(figsize=(10, 4))
sns.heatmap(
    aisle_counts.set_index("aisle").T,
    cmap="Reds",
    annot=True,
    fmt="d",
    ax=ax
)
ax.set_title("Aisle Congestion Heatmap @ 19:00 (Aisle B Bottleneck)")
st.pyplot(fig)

# ---------- Spoilage Risk ----------
st.subheader("🥶 Spoilage Risk — Temperature Violations")

warehouse_fixed = warehouse.rename(columns={"slot_id": "current_slot"})
temp_violations = sku_master.merge(warehouse_fixed, on="current_slot", how="left")
temp_violations = temp_violations[temp_violations["temp_req"] != temp_violations["temp_zone"]]

col1, col2 = st.columns(2)
col1.metric("SKUs Violating Temp Zones", len(temp_violations))
col2.metric("Total Inventory at Risk (kg)", f"{temp_violations['weight_kg'].sum():.1f}")

# ---------- Forklift Dead-Zone ----------
st.subheader("🚜 Forklift Dead-Zone — Aisle B Picker Density")

picker_movement["hour"] = picker_movement["order_timestamp"].dt.hour
picker_with_slot = picker_movement.merge(
    sku_master[["sku_id", "current_slot"]],
    on="sku_id",
    how="left"
)
picker_with_slot["aisle"] = picker_with_slot["current_slot"].str.extract(r"^([A-Z])")

aisle_b_density = (
    picker_with_slot[picker_with_slot["aisle"] == "B"]
    .groupby("hour")["picker_id"]
    .nunique()
    .reset_index()
)

fig, ax = plt.subplots(figsize=(10, 4))
ax.plot(aisle_b_density["hour"], aisle_b_density["picker_id"], marker="o")
ax.axhline(2, color="red", linestyle="--", label="Forklift Limit (2 pickers)")
ax.set_xlabel("Hour")
ax.set_ylabel("Active Pickers in Aisle B")
ax.set_title("Forklift Dead-Zone Constraint")
ax.legend()
st.pyplot(fig)

# ==================================================
# D. EXECUTIVE PITCH (40 pts)
# ==================================================
st.markdown("---")
st.header("🏛️ Executive Pitch — VelocityMart Board")

# ---------- Chaos Score ----------
st.subheader("🧠 Chaos Score — Warehouse Health Index")

temp_penalty = min(25, len(temp_violations) * 0.05)
shortcut_penalty = min(15, len(shortcut_pickers) * 5)
aisle_b_penalty = min(20, pct_b)

chaos_score = round(
    100 - temp_penalty - shortcut_penalty - aisle_b_penalty,
    1
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Chaos Score", f"{chaos_score}/100")
c2.metric("Temp Penalty", f"-{temp_penalty:.1f}")
c3.metric("Shortcut Penalty", f"-{shortcut_penalty:.1f}")
c4.metric("Aisle B Penalty", f"-{aisle_b_penalty:.1f}")

# ---------- Phase-1 Roadmap ----------
st.subheader("🚀 Phase-1 Roadmap — Top 50 SKUs to Move Tonight")

sku_velocity = orders.groupby("sku_id").size().reset_index(name="order_count")
phase1_skus = (
    sku_velocity
    .sort_values("order_count", ascending=False)
    .head(50)
    .merge(sku_master, on="sku_id", how="left")
)

st.dataframe(phase1_skus, use_container_width=True)

# ---------- Sensitivity Analysis ----------
st.subheader("📈 Sensitivity Analysis — 20% Order Spike")

peak_hour = orders_with_slot.groupby("hour").size().idxmax()
peak_orders_count = orders_with_slot[orders_with_slot["hour"] == peak_hour].shape[0]
active_pickers = picker_movement[picker_movement["hour"] == peak_hour]["picker_id"].nunique()

orders_per_picker = peak_orders_count / active_pickers
spike_orders = int(peak_orders_count * 1.2)
required_pickers = int(np.ceil(spike_orders / orders_per_picker))
additional_pickers = max(0, required_pickers - active_pickers)

s1, s2, s3 = st.columns(3)
s1.metric("Peak Hour Orders", peak_orders_count)
s2.metric("Orders After 20% Spike", spike_orders)
s3.metric("Extra Pickers Needed", additional_pickers)

if additional_pickers <= 2:
    st.success("🟢 HIGH RESILIENCE")
elif additional_pickers <= 4:
    st.warning("🟡 MEDIUM RESILIENCE")
else:
    st.error("🔴 LOW RESILIENCE")

# ==================================================
# FINAL SLOTTING PLAN
# ==================================================
st.markdown("---")
st.header("📦 Week 91 Final Slotting Plan")
st.dataframe(final_slotting.head(20), use_container_width=True)

st.download_button(
    "📥 Download Final Slotting Plan",
    final_slotting.to_csv(index=False),
    "final_slotting_plan.csv",
    "text/csv"
)

# ==================================================
# FOOTER
# ==================================================
st.markdown("---")
st.caption("VelocityMart | Bangalore Dark Store | DATAVERSE Challenge")
