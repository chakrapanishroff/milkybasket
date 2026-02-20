import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from io import StringIO

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Hotel Revenue Predictor",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Main background */
    .stApp { background-color: #f8f5f0; }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    }
    section[data-testid="stSidebar"] * { color: #e0e0e0 !important; }
    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] .stSlider label { color: #ffd700 !important; font-weight: 600; }

    /* Metric cards */
    [data-testid="metric-container"] {
        background: white;
        border: 1px solid #e0d5c5;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.07);
    }
    [data-testid="metric-container"] label { color: #7a6a55 !important; font-size: 0.8rem !important; }
    [data-testid="metric-container"] [data-testid="stMetricValue"] { color: #1a1a2e !important; font-size: 1.6rem !important; font-weight: 700; }

    /* Section headers */
    .section-header {
        background: linear-gradient(90deg, #1a1a2e, #0f3460);
        color: white !important;
        padding: 10px 20px;
        border-radius: 8px;
        font-size: 1.1rem;
        font-weight: 700;
        margin: 20px 0 12px 0;
        letter-spacing: 0.5px;
    }

    /* Prediction box */
    .pred-box {
        background: linear-gradient(135deg, #0f3460, #1a1a2e);
        color: white;
        padding: 28px 32px;
        border-radius: 16px;
        text-align: center;
        margin: 16px 0;
        box-shadow: 0 8px 24px rgba(15,52,96,0.3);
    }
    .pred-box h2 { color: #ffd700 !important; font-size: 2.5rem; margin: 0; }
    .pred-box p  { color: #c8d6e5; margin: 4px 0 0 0; font-size: 1rem; }

    /* Formula box */
    .formula-box {
        background: #fff8e7;
        border-left: 5px solid #ffd700;
        border-radius: 0 10px 10px 0;
        padding: 16px 20px;
        margin: 12px 0;
        font-family: monospace;
        font-size: 1.05rem;
        color: #1a1a2e;
        font-weight: 600;
    }

    /* Info banner */
    .info-banner {
        background: #e8f4f8;
        border: 1px solid #b3d9e8;
        border-radius: 10px;
        padding: 14px 18px;
        color: #1a4a5e;
        font-size: 0.92rem;
        margin: 10px 0;
    }

    /* Tables */
    .dataframe { font-size: 0.88rem !important; }

    /* Tabs */
    .stTabs [data-baseweb="tab"] { font-weight: 600; color: #1a1a2e; }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        border-bottom: 3px solid #0f3460;
        color: #0f3460;
    }

    /* Button */
    .stButton > button {
        background: linear-gradient(90deg, #0f3460, #1a1a2e);
        color: white !important;
        border: none;
        border-radius: 8px;
        padding: 10px 24px;
        font-weight: 700;
        font-size: 1rem;
        width: 100%;
        transition: opacity 0.2s;
    }
    .stButton > button:hover { opacity: 0.85; }

    /* R2 badge */
    .r2-badge {
        display: inline-block;
        background: #27ae60;
        color: white;
        border-radius: 20px;
        padding: 4px 14px;
        font-weight: 700;
        font-size: 1.1rem;
    }
    .r2-badge.moderate { background: #f39c12; }
    .r2-badge.poor { background: #e74c3c; }
</style>
""", unsafe_allow_html=True)


# ── Helper Functions ──────────────────────────────────────────────────────────
def compute_regression(x: np.ndarray, y: np.ndarray):
    """Return (beta0, beta1, r2, residuals, y_pred)."""
    n = len(x)
    x_mean, y_mean = x.mean(), y.mean()
    numerator   = np.sum((x - x_mean) * (y - y_mean))
    denominator = np.sum((x - x_mean) ** 2)
    beta1 = numerator / denominator
    beta0 = y_mean - beta1 * x_mean
    y_pred    = beta0 + beta1 * x
    residuals = y - y_pred
    ss_tot = np.sum((y - y_mean) ** 2)
    ss_res = np.sum(residuals ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 0
    return beta0, beta1, r2, residuals, y_pred

def r2_label(r2):
    if r2 >= 0.85: return "Excellent fit ✅", "good"
    if r2 >= 0.60: return "Moderate fit ⚠️", "moderate"
    return "Poor fit ❌", "poor"

def currency_fmt(val, symbol):
    if symbol == "₹":
        if val >= 1_00_000:
            return f"₹{val/1_00_000:.2f}L"
        return f"₹{val:,.0f}"
    return f"{symbol}{val:,.2f}"

def make_regression_plot(x, y, y_pred, x_label, y_label, symbol):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.patch.set_facecolor("#f8f5f0")

    # --- Scatter + regression line ---
    ax1 = axes[0]
    ax1.set_facecolor("#fdfcfa")
    ax1.scatter(x, y, color="#0f3460", s=90, zorder=5, label="Actual Data", edgecolors="white", linewidths=1.2)
    x_line = np.linspace(x.min(), x.max(), 200)
    beta0_plot = y.mean() - ((np.sum((x - x.mean())*(y - y.mean())) / np.sum((x - x.mean())**2)) * x.mean())
    beta1_plot  = np.sum((x - x.mean())*(y - y.mean())) / np.sum((x - x.mean())**2)
    ax1.plot(x_line, beta0_plot + beta1_plot * x_line, color="#e74c3c", linewidth=2.5, label="Regression Line")
    for xi, yi, yp in zip(x, y, y_pred):
        ax1.plot([xi, xi], [yi, yp], color="#bdc3c7", linewidth=1, linestyle="--", zorder=3)
    ax1.set_xlabel(x_label, fontsize=11, fontweight="bold", color="#333")
    ax1.set_ylabel(y_label, fontsize=11, fontweight="bold", color="#333")
    ax1.set_title("Regression Line & Actual Data", fontsize=13, fontweight="bold", color="#1a1a2e", pad=12)
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3, linestyle="--")
    ax1.spines[["top","right"]].set_visible(False)

    # --- Residual plot ---
    ax2 = axes[1]
    ax2.set_facecolor("#fdfcfa")
    residuals = y - y_pred
    colors = ["#27ae60" if r >= 0 else "#e74c3c" for r in residuals]
    ax2.bar(range(1, len(residuals)+1), residuals, color=colors, edgecolor="white", linewidth=0.8)
    ax2.axhline(0, color="#1a1a2e", linewidth=1.5, linestyle="-")
    ax2.set_xlabel("Observation Number", fontsize=11, fontweight="bold", color="#333")
    ax2.set_ylabel("Residual (Actual − Predicted)", fontsize=11, fontweight="bold", color="#333")
    ax2.set_title("Residual Analysis", fontsize=13, fontweight="bold", color="#1a1a2e", pad=12)
    pos_patch = mpatches.Patch(color="#27ae60", label="Over-predicted by model")
    neg_patch = mpatches.Patch(color="#e74c3c", label="Under-predicted by model")
    ax2.legend(handles=[pos_patch, neg_patch], fontsize=9)
    ax2.grid(True, alpha=0.3, linestyle="--", axis="y")
    ax2.spines[["top","right"]].set_visible(False)

    plt.tight_layout(pad=2)
    return fig


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏨 Hotel Revenue\nPredictor")
    st.markdown("---")

    st.markdown("### ⚙️ Setup")
    currency_options = {"Indian Rupee (₹)": "₹", "US Dollar ($)": "$", "Euro (€)": "€", "British Pound (£)": "£"}
    currency_choice  = st.selectbox("Currency", list(currency_options.keys()))
    symbol = currency_options[currency_choice]

    predictor_options = {
        "🛏️ Rooms Occupied":        "Rooms Occupied",
        "💰 Average Room Rate":     "Average Room Rate",
        "👥 Number of Guests":      "Number of Guests",
        "📅 Days Since Last Promo": "Days Since Last Promo",
        "🍽️ F&B Orders":            "F&B Orders",
        "✏️ Custom Variable":       "Custom",
    }
    predictor_choice = st.selectbox("Predictor Variable (X)", list(predictor_options.keys()))
    if predictor_options[predictor_choice] == "Custom":
        x_label = st.text_input("Enter X variable name", "Rooms Occupied")
    else:
        x_label = predictor_options[predictor_choice]

    outcome_options = {
        "💵 Daily Revenue":         "Daily Revenue",
        "😊 Guest Satisfaction Score": "Guest Satisfaction",
        "📦 Total Orders":          "Total Orders",
        "✏️ Custom Outcome":        "Custom",
    }
    outcome_choice = st.selectbox("Outcome Variable (Y)", list(outcome_options.keys()))
    if outcome_options[outcome_choice] == "Custom":
        y_label = st.text_input("Enter Y variable name", "Daily Revenue")
    else:
        y_label = outcome_options[outcome_choice]

    st.markdown("---")
    st.markdown("### 📋 About")
    st.markdown("""
This app uses **Simple Linear Regression**
to help hotel owners predict revenue and
other business outcomes from their own data.

**How to use:**
1. Set up your variables above
2. Enter your historical data
3. View the regression analysis
4. Make predictions!
    """)


# ── Main App ──────────────────────────────────────────────────────────────────
st.markdown("""
<div style='background:linear-gradient(90deg,#1a1a2e,#0f3460);padding:24px 32px;border-radius:16px;margin-bottom:24px'>
    <h1 style='color:#ffd700;margin:0;font-size:2rem'>🏨 Hotel Revenue Predictor</h1>
    <p style='color:#c8d6e5;margin:6px 0 0 0;font-size:1rem'>
        Powered by Linear Regression — Enter your hotel's data and get instant predictions
    </p>
</div>
""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["📥 Enter Data", "📊 Analysis", "🔮 Predict", "📚 Learn"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Data Entry
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown('<div class="section-header">📥 Enter Your Hotel\'s Historical Data</div>', unsafe_allow_html=True)

    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.markdown("#### Method 1 — Use Sample Data")
        sample_sets = {
            "📈 Rooms vs Revenue (8 days)": {
                "x": [20, 35, 40, 55, 60, 70, 80, 90],
                "y": [40000, 58000, 65000, 80000, 90000, 100000, 115000, 130000],
            },
            "💰 Room Rate vs Revenue": {
                "x": [1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000],
                "y": [85000, 105000, 130000, 160000, 185000, 215000, 240000, 270000],
            },
            "👥 Guests vs F&B Revenue": {
                "x": [30, 50, 70, 90, 110, 140, 160, 180],
                "y": [12000, 18500, 26000, 33000, 42000, 52000, 61000, 70000],
            },
        }
        sample_choice = st.selectbox("Choose a sample dataset", list(sample_sets.keys()))
        if st.button("Load Sample Data"):
            st.session_state["data_x"] = sample_sets[sample_choice]["x"]
            st.session_state["data_y"] = sample_sets[sample_choice]["y"]
            st.success("Sample data loaded! Go to the **Analysis** tab.")

        st.markdown("---")
        st.markdown("#### Method 2 — Paste CSV Data")
        st.markdown('<div class="info-banner">Paste two columns: first column = X values, second column = Y values. One row per line, comma-separated.</div>', unsafe_allow_html=True)
        csv_input = st.text_area(
            "Paste CSV here",
            placeholder="20,40000\n35,58000\n40,65000\n55,80000",
            height=160,
        )
        if st.button("Load CSV Data"):
            try:
                df_csv = pd.read_csv(StringIO(csv_input), header=None)
                st.session_state["data_x"] = df_csv.iloc[:, 0].tolist()
                st.session_state["data_y"] = df_csv.iloc[:, 1].tolist()
                st.success(f"✅ Loaded {len(st.session_state['data_x'])} rows!")
            except Exception as e:
                st.error(f"Could not parse CSV: {e}")

    with col_right:
        st.markdown("#### Method 3 — Enter Data Manually")

        n_rows = st.slider("Number of data points", min_value=4, max_value=20, value=8)

        # Build editable dataframe
        if "data_x" in st.session_state and len(st.session_state["data_x"]) == n_rows:
            init_x = st.session_state["data_x"]
            init_y = st.session_state["data_y"]
        else:
            init_x = [20, 35, 40, 55, 60, 70, 80, 90][:n_rows] + [50] * max(0, n_rows - 8)
            init_y = [40000, 58000, 65000, 80000, 90000, 100000, 115000, 130000][:n_rows] + [75000] * max(0, n_rows - 8)

        df_edit = pd.DataFrame({x_label: init_x[:n_rows], y_label: init_y[:n_rows]})
        edited = st.data_editor(df_edit, num_rows="fixed", use_container_width=True, height=320)

        if st.button("✅ Use This Data for Analysis"):
            st.session_state["data_x"] = edited[x_label].tolist()
            st.session_state["data_y"] = edited[y_label].tolist()
            st.success("Data saved! Head to the **Analysis** tab.")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Analysis
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    if "data_x" not in st.session_state:
        st.info("👈 Please enter or load data in the **Enter Data** tab first.")
    else:
        x = np.array(st.session_state["data_x"], dtype=float)
        y = np.array(st.session_state["data_y"], dtype=float)

        if len(x) < 3:
            st.error("Need at least 3 data points for regression.")
        else:
            beta0, beta1, r2, residuals, y_pred = compute_regression(x, y)

            # ── Key metrics ──
            st.markdown('<div class="section-header">📊 Regression Results</div>', unsafe_allow_html=True)
            m1, m2, m3, m4 = st.columns(4)
            fit_text, fit_class = r2_label(r2)
            m1.metric("Intercept (β₀)", f"{symbol}{beta0:,.2f}", help="Base value when X = 0")
            m2.metric("Slope (β₁)",     f"{symbol}{beta1:,.2f}", help="Change in Y per unit increase in X")
            m3.metric("R² Score",       f"{r2*100:.2f}%",        help="How well the model fits the data")
            m4.metric("Data Points",    len(x))

            # ── Formula ──
            st.markdown('<div class="section-header">📐 Your Hotel\'s Formula</div>', unsafe_allow_html=True)
            st.markdown(f"""
<div class="formula-box">
    {y_label}  =  {symbol}{beta0:,.2f}  +  ({symbol}{beta1:,.2f}  ×  {x_label})
</div>
""", unsafe_allow_html=True)

            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(f"""
<div class="info-banner">
<b>Intercept ({symbol}{beta0:,.2f})</b> — This is your hotel's base earning even before
considering {x_label.lower()}. It covers revenue from other facilities like restaurants,
parking, events, etc.
</div>""", unsafe_allow_html=True)
            with col_b:
                st.markdown(f"""
<div class="info-banner">
<b>Slope ({symbol}{beta1:,.2f})</b> — For every 1 unit increase in {x_label.lower()},
your {y_label.lower()} increases by {symbol}{beta1:,.2f}.
</div>""", unsafe_allow_html=True)

            # ── R² interpretation ──
            badge_class = fit_class
            st.markdown(f"""
<div style='margin:14px 0'>
    <b>Model Accuracy:</b> &nbsp;
    <span class='r2-badge {badge_class}'>{r2*100:.2f}% — {fit_text}</span>
    &nbsp;&nbsp; The model explains <b>{r2*100:.1f}%</b> of the variation in {y_label.lower()}.
</div>""", unsafe_allow_html=True)

            # ── Charts ──
            st.markdown('<div class="section-header">📈 Charts</div>', unsafe_allow_html=True)
            fig = make_regression_plot(x, y, y_pred, x_label, y_label, symbol)
            st.pyplot(fig, use_container_width=True)

            # ── Calculation Table ──
            st.markdown('<div class="section-header">🧮 Full Calculation Table</div>', unsafe_allow_html=True)
            x_mean, y_mean = x.mean(), y.mean()
            calc_df = pd.DataFrame({
                x_label:          x,
                y_label:          y,
                f"(x − x̄)":      np.round(x - x_mean, 4),
                f"(y − ȳ)":      np.round(y - y_mean, 4),
                "(x−x̄)(y−ȳ)":  np.round((x - x_mean)*(y - y_mean), 4),
                "(x−x̄)²":       np.round((x - x_mean)**2, 4),
                f"Predicted {y_label}": np.round(y_pred, 2),
                "Residual":       np.round(residuals, 2),
            })
            st.dataframe(calc_df, use_container_width=True)

            sums = pd.DataFrame({
                "(x−x̄)(y−ȳ)": [np.round(np.sum((x-x_mean)*(y-y_mean)), 4)],
                "(x−x̄)²":      [np.round(np.sum((x-x_mean)**2), 4)],
                "SSE":           [np.round(np.sum(residuals**2), 4)],
                "SST":           [np.round(np.sum((y-y_mean)**2), 4)],
            })
            st.markdown("**Column Sums:**")
            st.dataframe(sums, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Predict
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    if "data_x" not in st.session_state:
        st.info("👈 Please enter or load data in the **Enter Data** tab first.")
    else:
        x = np.array(st.session_state["data_x"], dtype=float)
        y = np.array(st.session_state["data_y"], dtype=float)
        beta0, beta1, r2, residuals, y_pred = compute_regression(x, y)

        st.markdown('<div class="section-header">🔮 Make a Prediction</div>', unsafe_allow_html=True)

        col_p1, col_p2 = st.columns([1, 1], gap="large")

        with col_p1:
            st.markdown(f"#### Enter a value for **{x_label}**")
            x_input = st.number_input(
                f"{x_label}",
                min_value=0.0,
                value=float(np.median(x)),
                step=1.0,
                format="%.2f",
            )

            prediction = beta0 + beta1 * x_input

            st.markdown(f"""
<div class='pred-box'>
    <p>Predicted {y_label}</p>
    <h2>{symbol}{prediction:,.2f}</h2>
    <p style='font-size:0.85rem;margin-top:10px'>
        = {symbol}{beta0:,.2f} + ({symbol}{beta1:,.2f} × {x_input:,.2f})
    </p>
</div>
""", unsafe_allow_html=True)

            # Confidence context
            x_min, x_max = x.min(), x.max()
            if x_input < x_min or x_input > x_max:
                st.warning(f"⚠️ Your input ({x_input}) is outside the range of your training data ({x_min:.0f}–{x_max:.0f}). Prediction may be less reliable.")
            else:
                st.success(f"✅ Input is within the training data range ({x_min:.0f}–{x_max:.0f}). Prediction is reliable.")

        with col_p2:
            st.markdown("#### 📋 Prediction Table — Multiple Values")
            n_pred = st.slider("How many scenarios?", 3, 10, 5)

            x_vals = np.linspace(x.min(), x.max() * 1.2, n_pred)
            pred_table = pd.DataFrame({
                x_label:                        np.round(x_vals, 1),
                f"Predicted {y_label}":         [f"{symbol}{(beta0 + beta1*v):,.2f}" for v in x_vals],
                "Change from prev":             ["—"] + [f"+{symbol}{(beta1*(x_vals[i]-x_vals[i-1])):,.2f}" for i in range(1, n_pred)],
            })
            st.dataframe(pred_table, use_container_width=True, hide_index=True)

        # ── Reverse prediction ──
        st.markdown('<div class="section-header">🔄 Reverse Prediction — What X do I need?</div>', unsafe_allow_html=True)
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            target_y = st.number_input(f"Target {y_label} ({symbol})", min_value=0.0, value=float(np.median(y)), step=100.0)
        with col_r2:
            if beta1 != 0:
                required_x = (target_y - beta0) / beta1
                st.markdown(f"""
<div class='pred-box' style='margin-top:8px'>
    <p>You need this many {x_label}</p>
    <h2>{required_x:,.1f}</h2>
    <p style='font-size:0.85rem;margin-top:8px'>to reach {symbol}{target_y:,.2f} in {y_label.lower()}</p>
</div>
""", unsafe_allow_html=True)
            else:
                st.error("Slope is zero — cannot reverse predict.")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Learn
# ═══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.markdown('<div class="section-header">📚 How Linear Regression Works</div>', unsafe_allow_html=True)

    st.markdown("""
### What is Linear Regression?

Linear regression finds the best straight line through your data. This line can then be used to
predict future values. Think of it as drawing the best possible trend line through your hotel's
historical performance data.

### The Formula

""")
    st.markdown("""
<div class="formula-box" style="font-size:1.2rem;text-align:center">
    Predicted Revenue  =  β₀  +  (β₁  ×  X)
</div>
""", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
**β₀ (Intercept)**
- The value of Y when X is zero
- Represents fixed/base revenue
- E.g. earnings from restaurant or parking regardless of room bookings

**β₁ (Slope)**
- How much Y changes for every 1-unit increase in X
- E.g. every additional room occupied adds ₹1,268 to revenue
        """)
    with col2:
        st.markdown("""
**R² (Accuracy Score)**
- Ranges from 0% to 100%
- 85%+ → Excellent model, very reliable predictions
- 60–85% → Moderate model, use with caution
- Below 60% → Poor model, other factors dominate

**Residuals**
- The difference between actual and predicted values
- Small, random residuals = good model
- Large or systematic residuals = model needs more variables
        """)

    st.markdown('<div class="section-header">📐 Step-by-Step Calculation Guide</div>', unsafe_allow_html=True)
    steps = [
        ("Step 1 — Collect Data", "Record your historical data — at least 5–10 observations for reliable results. More data = better predictions."),
        ("Step 2 — Calculate Means", "Find the average of X (x̄) and the average of Y (ȳ)."),
        ("Step 3 — Calculate Slope (β₁)", "β₁ = Σ(xᵢ − x̄)(yᵢ − ȳ) ÷ Σ(xᵢ − x̄)²"),
        ("Step 4 — Calculate Intercept (β₀)", "β₀ = ȳ − (β₁ × x̄)"),
        ("Step 5 — Build Your Formula", "Combine β₀ and β₁ into: ŷ = β₀ + β₁x"),
        ("Step 6 — Check R²", "R² = SSR ÷ SST. The closer to 100%, the better your model fits."),
        ("Step 7 — Make Predictions", "Plug in any X value into your formula to get the predicted Y."),
    ]
    for title, desc in steps:
        with st.expander(title):
            st.write(desc)

    st.markdown('<div class="section-header">🏨 Hotel Management Use Cases</div>', unsafe_allow_html=True)
    use_cases = {
        "💰 Revenue Forecasting":       "Predict tomorrow's revenue based on confirmed bookings.",
        "👷 Staff Scheduling":          "Predict how many staff you'll need based on expected occupancy.",
        "🍽️ F&B Planning":              "Forecast food & beverage demand based on number of guests.",
        "💸 Dynamic Pricing":           "Find the price elasticity — how much revenue changes with room rate.",
        "📣 Marketing ROI":             "Predict how many bookings result from a given marketing spend.",
        "😊 Guest Satisfaction":        "Identify which service metrics drive review scores.",
    }
    cols = st.columns(2)
    for i, (title, desc) in enumerate(use_cases.items()):
        with cols[i % 2]:
            st.markdown(f"""
<div style='background:white;border-radius:10px;padding:16px;margin:8px 0;
            border-left:4px solid #0f3460;box-shadow:0 2px 6px rgba(0,0,0,0.07)'>
    <b style='color:#0f3460'>{title}</b><br>
    <span style='color:#555;font-size:0.9rem'>{desc}</span>
</div>""", unsafe_allow_html=True)

    st.markdown('<div class="section-header">⚠️ Assumptions to Keep in Mind</div>', unsafe_allow_html=True)
    st.markdown("""
1. **Linearity** — The relationship between X and Y should be roughly linear (a straight-line pattern).
2. **Enough Data** — Aim for at least 10–15 observations for dependable results.
3. **No Extreme Outliers** — One very unusual day (e.g., a celebrity visit) can skew results.
4. **Consistent Conditions** — The relationship should be stable; major changes (renovations, new competitors) can break the model.
5. **Extrapolation Risk** — Predicting far beyond your data range becomes less reliable.
    """)

