# app.py

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="Telecom Solar Sizing Optimizer",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Business-logic imports ────────────────────────────────────────────────────
from src.data_loader import load_and_validate_data
from src.optimizer  import optimize_site, assess_existing_solar, get_justification
from src.utils      import RECTIFIER_LIMITS, TARIFF_KES, PANEL_RATING_KWP, INSTALLED_COST_KES
from src.report_generator import generate_executive_pdf

# ── Premium dark-mode styling ─────────────────────────────────────────────────
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@400;500;700&display=swap" rel="stylesheet">
<style>
    html, body, [class*="css"] { font-family: 'Outfit', sans-serif; }
    .stApp { background-color: #0b0f19; color: #f1f5f9; }
    h1, h2, h3 { font-family: 'Space Grotesk', sans-serif; font-weight: 700; }

    .header-text {
        background: linear-gradient(135deg, #38bdf8 0%, #818cf8 50%, #c084fc 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
    }

    section[data-testid="stSidebar"] {
        background-color: #0f172a !important;
        border-right: 1px solid #1e293b;
    }

    button[data-baseweb="tab"] {
        font-family: 'Space Grotesk', sans-serif;
        font-size: 1rem; font-weight: 500;
        color: #94a3b8 !important;
        border-bottom: 2px solid transparent !important;
        background-color: transparent !important;
        transition: all 0.3s ease;
    }
    button[data-baseweb="tab"]:hover   { color: #38bdf8 !important; }
    button[aria-selected="true"]        { color: #38bdf8 !important; border-bottom-color: #38bdf8 !important; }

    .metric-card {
        background: linear-gradient(135deg, rgba(30,41,59,0.45) 0%, rgba(15,23,42,0.65) 100%);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 16px;
        padding: 1.25rem;
        box-shadow: 0 4px 20px -2px rgba(0,0,0,0.35);
        transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
        margin-bottom: 1rem;
        position: relative;
        overflow: hidden;
    }
    .metric-card:hover {
        transform: translateY(-4px);
        border-color: rgba(99,102,241,0.45);
        box-shadow: 0 10px 25px -5px rgba(99,102,241,0.18);
    }
    .metric-card::before {
        content: ''; position: absolute; top: 0; left: 0;
        width: 100%; height: 4px;
        background: linear-gradient(90deg, #38bdf8, #818cf8, #c084fc);
    }
</style>
""", unsafe_allow_html=True)


# ── UI helpers ────────────────────────────────────────────────────────────────
def metric_card(title: str, value: str, subtitle: str = "", accent: str = "#818cf8"):
    st.markdown(f"""
    <div class="metric-card" style="border-left:4px solid {accent};">
        <div style="font-size:0.82rem;color:#94a3b8;font-weight:500;text-transform:uppercase;letter-spacing:0.05em;">{title}</div>
        <div style="font-size:1.8rem;font-weight:700;color:#f8fafc;margin-top:0.2rem;font-family:'Space Grotesk',sans-serif;">{value}</div>
        {f'<div style="font-size:0.78rem;color:#64748b;margin-top:0.2rem;">{subtitle}</div>' if subtitle else ''}
    </div>""", unsafe_allow_html=True)


def status_card(title: str, body: str, color: str):
    st.markdown(f"""
    <div style="background:rgba(30,41,59,0.4);border:1px solid {color};border-left:6px solid {color};
                border-radius:12px;padding:1.4rem;margin-bottom:1.2rem;">
        <h4 style="margin:0 0 0.6rem;color:{color};font-family:'Space Grotesk',sans-serif;">{title}</h4>
        <p  style="font-size:0.94rem;line-height:1.55;color:#f1f5f9;margin:0;">{body}</p>
    </div>""", unsafe_allow_html=True)


PLOTLY_BASE = dict(
    template='plotly_dark',
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(family='Outfit, sans-serif'),
)


# ── Data loading & optimisation (cached) ──────────────────────────────────────
@st.cache_data
def get_results(file_path: str):
    valid_df, exclusions = load_and_validate_data(file_path)

    rows = []
    for _, row in valid_df.iterrows():
        rec, _  = optimize_site(row)
        monthly_energy = row['Revised Average Load'] * 720.0
        assess = assess_existing_solar(row['PV Capacity (Kw)'], monthly_energy)
        just   = get_justification(row, rec, assess)

        # Calculated bill for existing solar (secondary reference)
        exist_solar_gen    = row['PV Capacity (Kw)'] * 132.0
        exist_offset       = min(exist_solar_gen, monthly_energy)
        calc_bill_existing = (monthly_energy - exist_offset) * TARIFF_KES

        rows.append({
            # ── Site info ────────────────────────────────────────────
            'No.':                              row['No.'],
            'Site Name':                        row['Site Name'],
            'Power Source':                     row['Power_Source'],
            'Rectifier Type':                   row['Rectifier Type'],
            'Rectifier Capacity (kWp)':         row['Rectifier Capacity'],
            'Existing PV Capacity (kWp)':       row['PV Capacity (Kw)'],
            'Revised Average Load (kW)':        row['Revised Average Load'],
            'Monthly Energy (kWh)':             monthly_energy,
            'Battery Capacity (AH)':            row['Battery Capacity (AH)'],
            'Battery Capacity (kWh)':           (row['Battery Capacity (AH)'] * 54.5) / 1000.0,
            # ── Bill baseline ────────────────────────────────────────
            'Actual Monthly Bill (KES)':        row['2026 Average Monthly Bill'],
            'Calculated Bill – Existing (KES)': calc_bill_existing,    # secondary
            # ── Optimisation outputs ─────────────────────────────────
            'Existing Solar Size Status':       assess['category'],
            'Panels to Add':                    rec['panels_added'],
            'Additional Solar (kWp)':           rec['additional_pv_kwp'],
            'Total Recommended PV (kWp)':       rec['total_pv_kwp'],
            'Rectifier Utilisation % (After)':  rec['rectifier_utilization'],
            'CAPEX (KES)':                      rec['capex_kes'],
            # ── Primary savings (vs. actual bill) ────────────────────
            'Monthly Savings (KES)':            rec['actual_monthly_savings_kes'],
            'Annual Savings (KES)':             rec['actual_annual_savings_kes'],
            'New Monthly Bill (KES)':           rec['actual_new_bill_kes'],
            # ── Financial returns ────────────────────────────────────
            'ROI %':                            rec['roi_pct'],
            'Payback Period (Years)':           rec['payback_years'],
            # ── Secondary (energy-model calculated bill after expansion) ──
            'Calculated Bill – After Expansion (KES)': rec['calculated_monthly_bill_kes'],
            # ── Narrative ───────────────────────────────────────────
            'Justification':                    just,
        })

    return valid_df, exclusions, pd.DataFrame(rows)


DATA_FILE = "Data/Sensitivity Project 2.0.xlsx"
try:
    valid_df, exclusions, results_df = get_results(DATA_FILE)
except Exception as exc:
    st.error(f"❌ Failed to load data: {exc}")
    st.stop()


# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.markdown('<h2 class="header-text">Settings</h2>', unsafe_allow_html=True)
st.sidebar.markdown("---")
st.sidebar.subheader("Engineering Parameters")
st.sidebar.metric("Electricity Tariff",      f"KES {TARIFF_KES:.2f} / kWh")
st.sidebar.metric("Standard Panel Rating",   f"{PANEL_RATING_KWP*1000:.0f} Wp ({PANEL_RATING_KWP:.3f} kWp)")
st.sidebar.metric("Installed Cost / Panel",  f"KES {INSTALLED_COST_KES:,.0f}")
st.sidebar.metric("Peak Sun Hours (PSH)",    "5.5 hrs / day")
st.sidebar.metric("System Efficiency",       "80%")
st.sidebar.markdown("---")
st.sidebar.caption(
    "**Savings are calculated against the actual 2026 Monthly Bill** — "
    "which already reflects existing solar. "
    "New-panel savings reduce that bill further."
)

n_valid    = len(valid_df)
n_excluded = len(exclusions)
if n_excluded:
    st.sidebar.warning(f"⚠️ {n_excluded} site(s) excluded — see Data Quality tab.")
else:
    st.sidebar.success(f"✅ All {n_valid} sites passed validation.")


# ── Page header ───────────────────────────────────────────────────────────────
hc1, hc2 = st.columns([6, 1])
with hc1:
    st.markdown('<h1 class="header-text">Telecom Solar Sizing Optimizer</h1>', unsafe_allow_html=True)
    st.markdown("##### Financially-Driven Solar PV Expansion Platform | Savings vs. Actual 2026 Grid Bill")
st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_overview, tab_ranking, tab_deepdive, tab_rectifier, tab_validation, tab_limitations = st.tabs([
    "📊 Portfolio Overview",
    "🏆 Opportunity Ranking",
    "🔍 Site Deep-Dive",
    "🔌 Rectifier Analysis",
    "📋 Data Quality",
    "⚠️ Model Limitations",
])


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 – PORTFOLIO OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════════
with tab_overview:
    col_t1, col_t2 = st.columns([4, 1])
    with col_t1:
        st.markdown("### Portfolio Investment Case")
    with col_t2:
        pdf_bytes = generate_executive_pdf(results_df)
        st.download_button(
            label="📄 Download Executive PDF",
            data=pdf_bytes,
            file_name=f"Solar_Expansion_Report_{pd.Timestamp.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

    # ── Compute portfolio-level aggregates ────────────────────────────────────
    total_capex          = results_df['CAPEX (KES)'].sum()
    total_monthly_sav    = results_df['Monthly Savings (KES)'].sum()
    total_annual_sav     = results_df['Annual Savings (KES)'].sum()
    total_add_pv         = results_df['Additional Solar (kWp)'].sum()
    total_exist_pv       = results_df['Existing PV Capacity (kWp)'].sum()
    total_new_pv         = results_df['Total Recommended PV (kWp)'].sum()
    portfolio_payback    = total_capex / total_annual_sav if total_annual_sav > 0 else 0.0
    portfolio_roi        = (total_annual_sav / total_capex * 100) if total_capex > 0 else 0.0
    total_actual_bill    = results_df['Actual Monthly Bill (KES)'].sum()
    total_new_bill       = results_df['New Monthly Bill (KES)'].sum()
    sites_with_expansion = int(results_df['Panels to Add'].gt(0).sum())
    total_panels         = int(results_df['Panels to Add'].sum())

    # ── Key metrics row ──────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: metric_card("Sites Analysed",          f"{n_valid}",
                          f"{n_excluded} excluded · {sites_with_expansion} need expansion", "#38bdf8")
    with c2: metric_card("Total Project CAPEX",     f"KES {total_capex:,.0f}",
                          f"{total_panels} panels across {sites_with_expansion} sites", "#818cf8")
    with c3: metric_card("Solar Capacity to Add",   f"{total_add_pv:.1f} kWp",
                          f"Existing: {total_exist_pv:.1f} → New: {total_new_pv:.1f} kWp", "#a78bfa")
    with c4: metric_card("Annual Grid Bill Savings", f"KES {total_annual_sav:,.0f}",
                          f"KES {total_monthly_sav:,.0f} saved / month", "#10b981")
    with c5: metric_card("Portfolio Payback",        f"{portfolio_payback:.2f} yrs",
                          f"Portfolio ROI: {portfolio_roi:.1f}%", "#f59e0b")

    st.markdown("---")

    # ── Bill before vs after ─────────────────────────────────────────────────
    st.markdown("#### Portfolio Grid Bill: Before vs. After Solar Expansion")
    bc1, bc2, bc3 = st.columns(3)
    with bc1: metric_card("Current Monthly Bill (All Sites)",
                           f"KES {total_actual_bill:,.0f}",
                           "Sum of actual 2026 bills", "#ef4444")
    with bc2: metric_card("Monthly Savings from Expansion",
                           f"KES {total_monthly_sav:,.0f}",
                           f"{total_monthly_sav/total_actual_bill*100:.1f}% bill reduction",
                           "#10b981")
    with bc3: metric_card("New Monthly Bill (After Expansion)",
                           f"KES {total_new_bill:,.0f}",
                           f"Annual: KES {total_new_bill*12:,.0f}", "#38bdf8")

    st.markdown("---")

    # ── Row of 3 charts ──────────────────────────────────────────────────────
    ch1, ch2, ch3 = st.columns(3)

    with ch1:
        st.markdown("#### Existing Solar Sizing Status")
        cat_counts = results_df['Existing Solar Size Status'].value_counts().reset_index()
        cat_counts.columns = ['Status', 'Count']
        colour_map = {
            'Under-sized': '#ef4444', 'Adequately sized': '#f59e0b',
            'Near optimum': '#10b981', 'Over-sized': '#8b5cf6',
        }
        fig_pie = px.pie(cat_counts, values='Count', names='Status',
                         color='Status', color_discrete_map=colour_map, hole=0.55)
        fig_pie.update_traces(
            textinfo='value+percent', 
            textfont_size=14,
            textfont_color='white',
            hovertemplate="<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}<extra></extra>",
            marker=dict(line=dict(color='#0b0f19', width=2))
        )
        fig_pie.update_layout(**PLOTLY_BASE,
                              legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center"),
                              margin=dict(t=20, b=20, l=20, r=20))
        st.plotly_chart(fig_pie, use_container_width=True)

    with ch2:
        st.markdown("#### Top 15 Sites — Monthly Bill Savings (KES)")
        top15_sav = (results_df[results_df['Monthly Savings (KES)'] > 0]
                     .nlargest(15, 'Monthly Savings (KES)'))
        fig_sav = go.Figure()
        fig_sav.add_trace(go.Bar(
            y=top15_sav['Site Name'], x=top15_sav['Monthly Savings (KES)'],
            orientation='h', 
            marker=dict(
                color=top15_sav['Monthly Savings (KES)'],
                colorscale=['#064e3b', '#10b981', '#34d399'],
                line=dict(color='rgba(255,255,255,0.1)', width=1)
            ),
            text=top15_sav['Monthly Savings (KES)'].apply(lambda v: f"KES {v:,.0f}"),
            textposition='outside',
            textfont=dict(color='white'),
            hovertemplate="<b>%{y}</b><br>Savings: KES %{x:,.0f}<extra></extra>"
        ))
        fig_sav.update_layout(**PLOTLY_BASE,
                              xaxis=dict(title='Monthly Savings (KES)', showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
                              yaxis=dict(autorange='reversed', showgrid=False),
                              height=450, margin=dict(l=10, r=90, t=20, b=30),
                              hovermode="y unified")
        st.plotly_chart(fig_sav, use_container_width=True)

    with ch3:
        st.markdown("#### Bill Breakdown by Rectifier Type")
        rect_bills = results_df.groupby('Rectifier Type').agg(
            Before=('Actual Monthly Bill (KES)', 'sum'),
            After=('New Monthly Bill (KES)', 'sum'),
        ).reset_index()
        rect_bills['Savings'] = rect_bills['Before'] - rect_bills['After']

        fig_rb = go.Figure()
        fig_rb.add_trace(go.Bar(name='Current Bill', x=rect_bills['Rectifier Type'],
                                y=rect_bills['Before'], marker_color='#ef4444',
                                marker_line=dict(width=1, color='rgba(255,255,255,0.1)'),
                                hovertemplate="KES %{y:,.0f}"))
        fig_rb.add_trace(go.Bar(name='New Bill',     x=rect_bills['Rectifier Type'],
                                y=rect_bills['After'],  marker_color='#38bdf8',
                                marker_line=dict(width=1, color='rgba(255,255,255,0.1)'),
                                hovertemplate="KES %{y:,.0f}"))
        fig_rb.add_trace(go.Bar(name='Savings',      x=rect_bills['Rectifier Type'],
                                y=rect_bills['Savings'], marker_color='#10b981',
                                marker_line=dict(width=1, color='rgba(255,255,255,0.1)'),
                                hovertemplate="KES %{y:,.0f}"))
        fig_rb.update_layout(**PLOTLY_BASE, barmode='group',
                              yaxis=dict(title='KES / Month', showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
                              xaxis=dict(showgrid=False),
                              legend=dict(orientation="h", y=1.15, x=0.5, xanchor="center"),
                              height=450, margin=dict(t=30, b=30),
                              hovermode="x unified")
        st.plotly_chart(fig_rb, use_container_width=True)

    st.markdown("---")

    # ── Per-site bill comparison (before vs after) ───────────────────────────
    st.markdown("#### Per-Site Monthly Bill — Before vs. After Expansion")
    bill_chart_df = (results_df[results_df['Monthly Savings (KES)'] > 0]
                     .sort_values('Actual Monthly Bill (KES)', ascending=False)
                     .head(25).copy())
    fig_bill = go.Figure()
    fig_bill.add_trace(go.Bar(
        name='Current Monthly Bill',
        x=bill_chart_df['Site Name'],
        y=bill_chart_df['Actual Monthly Bill (KES)'],
        marker_color='#ef4444',
        marker_line=dict(width=1, color='rgba(255,255,255,0.1)'),
        hovertemplate="KES %{y:,.0f}"
    ))
    fig_bill.add_trace(go.Bar(
        name='New Monthly Bill (After Expansion)',
        x=bill_chart_df['Site Name'],
        y=bill_chart_df['New Monthly Bill (KES)'],
        marker_color='#38bdf8',
        marker_line=dict(width=1, color='rgba(255,255,255,0.1)'),
        hovertemplate="KES %{y:,.0f}"
    ))
    fig_bill.update_layout(**PLOTLY_BASE, barmode='group',
                            xaxis=dict(tickangle=45, showgrid=False),
                            yaxis=dict(title='Monthly Bill (KES)', showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
                            legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center"),
                            hovermode="x unified",
                            height=480, margin=dict(t=20, b=20))
    st.plotly_chart(fig_bill, use_container_width=True)

    # ── ROI Consistency Explanation ──────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### ℹ️ Why ROI & Payback Are Consistent Across Most Sites")
    st.info(
        "You may notice that ROI (**86.5%**) and Payback (**1.16 years**) are nearly "
        "identical across most sites. This is **mathematically correct** and expected.\n\n"
        "**Reason:** Each solar panel has identical marginal economics:\n"
        f"- Each panel generates: `{PANEL_RATING_KWP} kWp × 132 kWh/kWp/month = "
        f"{PANEL_RATING_KWP * 132:.1f} kWh/month`\n"
        f"- Each panel saves: `{PANEL_RATING_KWP * 132:.1f} kWh × KES {TARIFF_KES:.0f} = "
        f"KES {PANEL_RATING_KWP * 132 * TARIFF_KES:,.2f}/month` "
        f"(KES {PANEL_RATING_KWP * 132 * TARIFF_KES * 12:,.2f}/year)\n"
        f"- Each panel costs: `KES {INSTALLED_COST_KES:,.0f}`\n"
        f"- Per-panel ROI = `{PANEL_RATING_KWP * 132 * TARIFF_KES * 12:,.2f} ÷ {INSTALLED_COST_KES:,.0f} × 100 "
        f"= {PANEL_RATING_KWP * 132 * TARIFF_KES * 12 / INSTALLED_COST_KES * 100:.1f}%`\n\n"
        "Since this ratio is **constant per panel**, and since for most sites the new panel "
        "generation is well below the current grid energy (no saturation cap), every panel "
        "added has the same marginal return — making the ROI identical regardless of how "
        "many panels are added.\n\n"
        "ROI **differs only** when a site's small bill causes the savings cap to activate "
        "(new generation exceeds current grid purchases), reducing the effective savings per panel."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 – OPPORTUNITY RANKING
# ═══════════════════════════════════════════════════════════════════════════════
with tab_ranking:
    st.markdown("### Solar Expansion Opportunity Ranking")
    st.markdown(
        "All savings are calculated against each site's actual **2026 Average Monthly Bill**. "
        "Differentiate sites by **absolute savings potential** rather than ROI (which is uniform — see Portfolio Overview for explanation)."
    )

    r1, r2, r3 = st.columns(3)
    with r1:
        sort_by = st.selectbox("Rank by:", [
            "Highest Annual Savings (KES)",
            "Best ROI %",
            "Fastest Payback (Years)",
            "Highest CAPEX (KES)",
        ])
    with r2:
        rect_filter = st.multiselect("Rectifier Type:",
                                     results_df['Rectifier Type'].unique(),
                                     default=list(results_df['Rectifier Type'].unique()))
    with r3:
        status_filter = st.multiselect("Existing Solar Status:",
                                       results_df['Existing Solar Size Status'].unique(),
                                       default=list(results_df['Existing Solar Size Status'].unique()))

    fdf = results_df[
        results_df['Rectifier Type'].isin(rect_filter) &
        results_df['Existing Solar Size Status'].isin(status_filter)
    ].copy()

    if sort_by == "Highest Annual Savings (KES)":
        fdf = fdf.sort_values('Annual Savings (KES)', ascending=False)
    elif sort_by == "Best ROI %":
        fdf = fdf.sort_values('ROI %', ascending=False)
    elif sort_by == "Fastest Payback (Years)":
        fdf['_pb'] = fdf['Payback Period (Years)'].apply(lambda x: float('inf') if x == 0 else x)
        fdf = fdf.sort_values('_pb').drop(columns=['_pb'])
    elif sort_by == "Highest CAPEX (KES)":
        fdf = fdf.sort_values('CAPEX (KES)', ascending=False)

    display = fdf[[
        'Site Name', 'Rectifier Type', 'Existing PV Capacity (kWp)',
        'Revised Average Load (kW)', 'Existing Solar Size Status',
        'Actual Monthly Bill (KES)',
        'Panels to Add', 'Additional Solar (kWp)',
        'CAPEX (KES)',
        'Monthly Savings (KES)', 'Annual Savings (KES)',
        'New Monthly Bill (KES)',
        'ROI %', 'Payback Period (Years)',
        'Calculated Bill – After Expansion (KES)',
    ]].copy()

    display.columns = [
        'Site', 'Rectifier', 'Exist PV (kWp)', 'Avg Load (kW)', 'Solar Status',
        'Current Bill (KES)',
        'Panels +', 'Add Solar (kWp)',
        'CAPEX (KES)',
        'Monthly Savings (KES)', 'Annual Savings (KES)',
        'New Bill (KES)',
        'ROI %', 'Payback (Yrs)',
        'Calc Bill After (KES) ⓘ',
    ]

    st.dataframe(
        display.style.format({
            'Exist PV (kWp)':           '{:.2f}',
            'Avg Load (kW)':            '{:.2f}',
            'Add Solar (kWp)':          '{:.3f}',
            'Current Bill (KES)':       '{:,.2f}',
            'CAPEX (KES)':              '{:,.2f}',
            'Monthly Savings (KES)':    '{:,.2f}',
            'Annual Savings (KES)':     '{:,.2f}',
            'New Bill (KES)':           '{:,.2f}',
            'ROI %':                    '{:.1f}%',
            'Payback (Yrs)':            '{:.2f}',
            'Calc Bill After (KES) ⓘ': '{:,.2f}',
        }),
        use_container_width=True,
        hide_index=True,
    )
    st.caption("ⓘ *Calc Bill After* is a secondary reference computed from the energy model (Revised Average Load × 720 h). "
               "The primary savings figure uses the actual 2026 Monthly Bill as baseline.")

    csv = display.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download Full Report (CSV)", csv,
                       "solar_expansion_recommendations.csv", "text/csv",
                       key="dl-csv")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 – SITE DEEP-DIVE
# ═══════════════════════════════════════════════════════════════════════════════
with tab_deepdive:
    st.markdown("### Site-Level Sizing Deep-Dive")

    selected = st.selectbox("Select a Telecom Site:",
                            sorted(results_df['Site Name'].tolist()))

    site_row  = valid_df[valid_df['Site Name'] == selected].iloc[0]
    site_res  = results_df[results_df['Site Name'] == selected].iloc[0]
    rec, scenarios = optimize_site(site_row)
    scen_df = pd.DataFrame(scenarios)

    dc1, dc2 = st.columns(2)

    # ── Left column: Technical baseline ──────────────────────────────────────
    with dc1:
        st.markdown("#### Technical & Operational Baseline")

        monthly_energy  = site_row['Revised Average Load'] * 720.0
        exist_solar_gen = site_row['PV Capacity (Kw)'] * 132.0
        exist_offset    = min(exist_solar_gen, monthly_energy)
        calc_bill_exist = (monthly_energy - exist_offset) * TARIFF_KES

        specs = {
            'Parameter': [
                'Site ID / No.',
                'Revised Average Load (kW)',
                'Daily Energy (kWh/day)',
                'Monthly Energy (kWh/month)',
                'Existing PV Capacity (kWp)',
                'Rectifier Type',
                'Rectifier Solar Limit (kWp)',
                'Battery Bank (Ah)',
                'Battery Bank (kWh at 54.5V)',
                '── Bill & Baseline ──',
                'Actual 2026 Monthly Bill (KES)',
                'Calculated Bill – Existing Solar (KES)',
            ],
            'Value': [
                str(site_row['No.']),
                f"{site_row['Revised Average Load']:.2f} kW",
                f"{site_row['Revised Average Load'] * 24:.2f} kWh",
                f"{monthly_energy:.2f} kWh",
                f"{site_row['PV Capacity (Kw)']:.2f} kWp",
                site_row['Rectifier Type'],
                f"{RECTIFIER_LIMITS[site_row['Rectifier Type']]:.1f} kWp",
                f"{site_row['Battery Capacity (AH)']:.0f} Ah",
                f"{(site_row['Battery Capacity (AH)'] * 54.5)/1000:.2f} kWh",
                '',
                f"KES {site_row['2026 Average Monthly Bill']:,.2f}",
                f"KES {calc_bill_exist:,.2f}",
            ],
        }
        st.table(pd.DataFrame(specs))

    # ── Right column: Assessment + Recommendation ─────────────────────────────
    with dc2:
        st.markdown("#### Existing Asset Sizing Assessment")
        assess = assess_existing_solar(site_row['PV Capacity (Kw)'], monthly_energy)
        status_colour = {
            'Under-sized': '#ef4444', 'Adequately sized': '#f59e0b',
            'Near optimum': '#10b981', 'Over-sized': '#8b5cf6',
        }.get(assess['category'], '#818cf8')
        status_card(f"Status: {assess['category'].upper()}",
                    assess['justification'], status_colour)

        st.markdown("#### Recommended Expansion Decision")
        if site_res['Panels to Add'] > 0:
            status_card("✅ APPROVED INVESTMENT PLAN",
                        site_res['Justification'], '#10b981')
        else:
            status_card("ℹ️ NO EXPANSION RECOMMENDED",
                        site_res['Justification'], '#94a3b8')

        # Quick summary metrics
        if site_res['Panels to Add'] > 0:
            sm1, sm2, sm3 = st.columns(3)
            with sm1: st.metric("CAPEX",            f"KES {site_res['CAPEX (KES)']:,.0f}")
            with sm2: st.metric("Monthly Savings",  f"KES {site_res['Monthly Savings (KES)']:,.0f}")
            with sm3: st.metric("Payback",          f"{site_res['Payback Period (Years)']:.2f} yrs")

    st.markdown("---")
    st.markdown("#### Scenario Evaluation Engine")
    sc1, sc2 = st.columns(2)

    with sc1:
        fig_inv = make_subplots(specs=[[{"secondary_y": True}]])
        fig_inv.add_trace(go.Bar(x=scen_df['panels_added'], y=scen_df['capex_kes'],
                                 name='CAPEX (KES)', marker_color='#818cf8', opacity=0.75),
                          secondary_y=False)
        fig_inv.add_trace(go.Scatter(x=scen_df['panels_added'],
                                     y=scen_df['actual_annual_savings_kes'],
                                     name='Annual Savings vs Actual Bill (KES)',
                                     mode='lines+markers',
                                     line=dict(color='#10b981', width=3),
                                     marker=dict(size=7)),
                          secondary_y=True)
        fig_inv.add_vline(x=rec['panels_added'], line_dash='dash',
                          line_color='#ef4444', line_width=2,
                          annotation_text="Recommended", annotation_position="top right")
        fig_inv.update_layout(**PLOTLY_BASE,
                              title=f"CAPEX vs. Annual Savings — {selected}",
                              xaxis=dict(title='Panels Added'),
                              legend=dict(orientation="h", y=1.15))
        fig_inv.update_yaxes(title_text="CAPEX (KES)", secondary_y=False)
        fig_inv.update_yaxes(title_text="Annual Savings (KES)", secondary_y=True)
        st.plotly_chart(fig_inv, use_container_width=True)

    with sc2:
        scen_pos = scen_df[scen_df['panels_added'] > 0]
        fig_ret = make_subplots(specs=[[{"secondary_y": True}]])
        fig_ret.add_trace(go.Scatter(x=scen_pos['panels_added'], y=scen_pos['roi_pct'],
                                     name='ROI %', mode='lines+markers',
                                     line=dict(color='#c084fc', width=3),
                                     marker=dict(size=7)),
                          secondary_y=False)
        fig_ret.add_trace(go.Scatter(x=scen_pos['panels_added'],
                                     y=scen_pos['payback_years'],
                                     name='Payback (Years)', mode='lines+markers',
                                     line=dict(color='#f59e0b', width=3),
                                     marker=dict(size=7)),
                          secondary_y=True)
        fig_ret.add_vline(x=rec['panels_added'], line_dash='dash',
                          line_color='#ef4444', line_width=2)
        fig_ret.update_layout(**PLOTLY_BASE,
                              title=f"ROI & Payback vs. Panels Added — {selected}",
                              xaxis=dict(title='Panels Added'),
                              legend=dict(orientation="h", y=1.15))
        fig_ret.update_yaxes(title_text="ROI (%)", secondary_y=False)
        fig_ret.update_yaxes(title_text="Payback (Years)", secondary_y=True)
        st.plotly_chart(fig_ret, use_container_width=True)

    # ── Full scenario ledger ──────────────────────────────────────────────────
    st.markdown("#### Full Scenario Calculation Ledger")
    st.caption("Primary savings are vs. the actual 2026 Monthly Bill. "
               "Calculated Bill is a secondary energy-model reference.")

    ledger = scen_df[[
        'panels_added', 'additional_pv_kwp', 'total_pv_kwp',
        'rectifier_utilization', 'monthly_solar_production_kwh',
        'solar_contribution_pct',
        'capex_kes',
        'actual_monthly_savings_kes', 'actual_annual_savings_kes',
        'actual_new_bill_kes',
        'roi_pct', 'payback_years',
        'calculated_monthly_bill_kes',
    ]].copy()

    ledger.columns = [
        'Panels +', 'Add PV (kWp)', 'Total PV (kWp)',
        'Rect Util %', 'Solar Gen (kWh/mo)',
        'Solar Contrib %',
        'CAPEX (KES)',
        'Monthly Savings (KES)', 'Annual Savings (KES)',
        'New Grid Bill (KES)',
        'ROI %', 'Payback (Yrs)',
        'Calc Bill – Energy Model (KES)',
    ]

    st.dataframe(
        ledger.style.format({
            'Add PV (kWp)':               '{:.3f}',
            'Total PV (kWp)':             '{:.3f}',
            'Rect Util %':                '{:.1f}%',
            'Solar Gen (kWh/mo)':         '{:,.1f}',
            'Solar Contrib %':            '{:.1f}%',
            'CAPEX (KES)':                '{:,.2f}',
            'Monthly Savings (KES)':      '{:,.2f}',
            'Annual Savings (KES)':       '{:,.2f}',
            'New Grid Bill (KES)':        '{:,.2f}',
            'ROI %':                      '{:.1f}%',
            'Payback (Yrs)':              '{:.2f}',
            'Calc Bill – Energy Model (KES)': '{:,.2f}',
        }),
        use_container_width=True,
        hide_index=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 – RECTIFIER ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_rectifier:
    st.markdown("### Rectifier Capacity & Headroom Analysis")
    st.markdown("Shows how solar capacity utilises each rectifier type, before and after the recommended expansion.")

    rect_grp = results_df.groupby('Rectifier Type').agg(
        Sites=('Site Name', 'count'),
        Limit_kWp=('Rectifier Capacity (kWp)', 'mean'),
        Exist_PV=('Existing PV Capacity (kWp)', 'mean'),
        Rec_PV=('Total Recommended PV (kWp)', 'mean'),
    ).reset_index()
    rect_grp['Exist Util %']  = (rect_grp['Exist_PV'] / rect_grp['Limit_kWp']) * 100
    rect_grp['Rec Util %']    = (rect_grp['Rec_PV']   / rect_grp['Limit_kWp']) * 100
    rect_grp['Headroom (kWp)']= rect_grp['Limit_kWp'] - rect_grp['Rec_PV']

    rg1, rg2 = st.columns([2, 1])
    with rg1:
        st.markdown("#### Rectifier Utilisation Summary")
        st.dataframe(rect_grp.style.format({
            'Limit_kWp': '{:.1f}', 'Exist_PV': '{:.2f}', 'Rec_PV': '{:.2f}',
            'Exist Util %': '{:.1f}%', 'Rec Util %': '{:.1f}%',
            'Headroom (kWp)': '{:.2f}',
        }), use_container_width=True, hide_index=True)
    with rg2:
        st.markdown("#### Remaining Headroom")
        for _, rr in rect_grp.iterrows():
            st.metric(f"{rr['Rectifier Type']}",
                      f"{rr['Headroom (kWp)']:.2f} kWp",
                      f"After: {rr['Rec Util %']:.1f}% utilisation")

    st.markdown("---")
    fig_rect = go.Figure()
    fig_rect.add_trace(go.Bar(x=rect_grp['Rectifier Type'],
                               y=rect_grp['Exist Util %'],
                               name='Before Expansion',
                               marker_color='#ef4444', opacity=0.8))
    fig_rect.add_trace(go.Bar(x=rect_grp['Rectifier Type'],
                               y=rect_grp['Rec Util %'],
                               name='After Recommended Expansion',
                               marker_color='#10b981', opacity=0.8))
    fig_rect.update_layout(**PLOTLY_BASE,
                            yaxis=dict(title='Average Utilisation %', range=[0, 100]),
                            legend=dict(orientation="h", y=1.15))
    st.plotly_chart(fig_rect, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5 – DATA QUALITY & EXCLUSIONS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_validation:
    st.markdown("### Data Quality & Exclusion Report")
    st.markdown("Every site in the source file is accounted for. "
                "Excluded sites are listed with specific reasons.")

    vc1, vc2, vc3 = st.columns(3)
    with vc1: metric_card("Total Sites in File",   f"{n_valid + n_excluded}", "Source dataset size", "#38bdf8")
    with vc2: metric_card("Valid / Processed",     f"{n_valid}", "Passed all quality checks", "#10b981")
    with vc3: metric_card("Excluded Sites",        f"{n_excluded}",
                           "Failed one or more checks",
                           "#ef4444" if n_excluded > 0 else "#10b981")

    st.markdown("---")

    if n_excluded > 0:
        st.markdown("#### Excluded Sites Ledger")
        st.info(
            "Sites are excluded only when critical data is missing or invalid. "
            "The most common reasons are: **zero 2026 Monthly Bill** "
            "(no billing baseline for savings calculation) and "
            "**zero Revised Average Load** (no energy demand to model)."
        )
        ex_df = pd.DataFrame(exclusions)
        ex_show = ex_df[[
            'No.', 'Site Name', 'Rectifier Type', 'Rectifier Capacity',
            'PV Capacity (Kw)', '2026 Average Monthly Bill',
            'Revised Average Load', 'Reason',
        ]].copy()
        ex_show.columns = [
            'No.', 'Site Name', 'Rectifier', 'Rect Cap (kWp)',
            'Exist PV (kWp)', 'Monthly Bill (KES)',
            'Revised Load (kW)', 'Exclusion Reason',
        ]
        st.dataframe(ex_show, use_container_width=True, hide_index=True)
    else:
        st.success("🎉 All sites passed validation — zero exclusions.")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 6 – MODEL LIMITATIONS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_limitations:
    st.markdown("### Engineering & Financial Limitations")
    st.markdown("While this mathematical model provides robust, conservative estimates for solar ROI, it makes several critical assumptions. Below are the key limitations to be aware of when presenting these figures to stakeholders.")

    st.markdown("---")

    c1, c2 = st.columns(2)

    with c1:
        st.info("**1. Battery Constraints & Wasted Energy**")
        st.markdown(
            "The model currently simulates **daytime load offset only**. It does not size or "
            "calculate the financials for Lithium-Ion battery storage. Therefore, if a solar array generates "
            "excess power during the day beyond what the site consumes, that energy is mathematically 'spilled' (wasted). "
            "In reality, adding batteries would capture this energy to offset the night-time grid bill, potentially "
            "increasing the overall site ROI."
        )

        st.warning("**2. Reliance on KPLC Bill Accuracy**")
        st.markdown(
            "The entire financial baseline relies on the `2026 Average Monthly Bill` column. If KPLC is estimating bills, "
            "relying on faulty meters, or if there are severe grid outages causing the site to run on diesel generators, "
            "the actual energy consumed by the site might be much higher than the bill suggests. If the bill is artificially low, "
            "the model will incorrectly recommend smaller solar arrays."
        )

        st.error("**3. Fixed Grid Tariffs (No Inflation)**")
        st.markdown(
            "The ROI and Payback calculations assume a flat grid tariff of **KES 28/kWh** in perpetuity. "
            "It does not factor in annual tariff inflation. If KPLC raises prices next year, the true "
            "savings and ROI of these solar panels will actually be **higher** than what is projected here."
        )

    with c2:
        st.info("**4. No Net-Metering**")
        st.markdown(
            "The model assumes that it is impossible to sell excess power back to the grid (no net-metering). "
            "The 'Savings Cap' physically prevents the financial savings from exceeding the current KPLC bill. "
            "If legislation changes to allow power sales, 'Over-sized' solar sites could become revenue-generating assets."
        )

        st.warning("**5. Simplified Production Curve**")
        st.markdown(
            "Solar generation is calculated using a flat `Peak Sun Hours (PSH)` of 5.5 hours per day, averaged across the year. "
            "It does not account for hourly production curves, seasonal rainy months, or site-specific shading (trees, buildings). "
            "A detailed PVsyst simulation is recommended before physical deployment."
        )

        st.error("**6. Undocumented Site Loads**")
        st.markdown(
            "The `Revised Average Load` is used for theoretical engineering checks. However, telecom sites often have "
            "undocumented loads (security lights, AC units) that draw heavily from the meter. If these loads are present, "
            "the KPLC bill will be high, but our engineering math might look mismatched. A physical site audit is required to confirm loads."
        )

    st.markdown("---")
    st.caption("*Phase 2 Recommendation: Integrate battery autonomy sizing and NPV (Net Present Value) calculations to resolve limitations 1 and 3.*")
