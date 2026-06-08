# app.py

import streamlit as pd_st
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Set page configuration first
st.set_page_config(
    page_title="Telecom Solar Sizing Optimizer",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Import business logic modules
from src.data_loader import load_and_validate_data
from src.optimizer import optimize_site, assess_existing_solar, get_justification
from src.utils import RECTIFIER_LIMITS, TARIFF_KES, PANEL_RATING_KWP, INSTALLED_COST_KES

# Inject Premium custom styling and fonts
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@400;500;700&display=swap" rel="stylesheet">
<style>
    /* Global Styles */
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    .stApp {
        background-color: #0b0f19;
        color: #f1f5f9;
    }
    
    h1, h2, h3, .title-font {
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 700;
    }
    
    /* Gradient headers */
    .header-text {
        background: linear-gradient(135deg, #38bdf8 0%, #818cf8 50%, #c084fc 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #0f172a !important;
        border-right: 1px solid #1e293b;
    }
    
    /* Tabs custom styling */
    button[data-baseweb="tab"] {
        font-family: 'Space Grotesk', sans-serif;
        font-size: 1.05rem;
        font-weight: 500;
        color: #94a3b8 !important;
        border-bottom: 2px solid transparent !important;
        background-color: transparent !important;
        transition: all 0.3s ease;
    }
    
    button[data-baseweb="tab"]:hover {
        color: #38bdf8 !important;
    }
    
    button[aria-selected="true"] {
        color: #38bdf8 !important;
        border-bottom-color: #38bdf8 !important;
    }
    
    /* Metric Card styling */
    .metric-card-container {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.4) 0%, rgba(15, 23, 42, 0.6) 100%);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 16px;
        padding: 1.25rem;
        box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.3);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        margin-bottom: 1rem;
        position: relative;
        overflow: hidden;
    }
    
    .metric-card-container:hover {
        transform: translateY(-4px);
        border-color: rgba(99, 102, 241, 0.4);
        box-shadow: 0 10px 25px -5px rgba(99, 102, 241, 0.15);
    }
    
    .metric-card-container::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 4px;
        background: linear-gradient(90deg, #38bdf8, #818cf8, #c084fc);
        opacity: 0.8;
    }
    
    /* Status Badge styling */
    .badge {
        display: inline-block;
        padding: 0.25em 0.6em;
        font-size: 75%;
        font-weight: 700;
        line-height: 1;
        text-align: center;
        white-space: nowrap;
        vertical-align: baseline;
        border-radius: 0.375rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .badge-undersized { background-color: #ef4444; color: #fff; }
    .badge-adequate { background-color: #f59e0b; color: #fff; }
    .badge-optimum { background-color: #10b981; color: #fff; }
    .badge-oversized { background-color: #8b5cf6; color: #fff; }
    
</style>
""", unsafe_allow_html=True)


# Custom UI helper functions
def render_metric_card(title: str, value: str, subtitle: str = "", border_accent: str = "#818cf8"):
    st.markdown(f"""
    <div class="metric-card-container" style="border-left: 4px solid {border_accent};">
        <div style="font-size: 0.85rem; color: #94a3b8; font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em;">{title}</div>
        <div style="font-size: 1.85rem; font-weight: 700; color: #f8fafc; margin-top: 0.25rem; font-family: 'Space Grotesk', sans-serif;">{value}</div>
        {f'<div style="font-size: 0.8rem; color: #64748b; margin-top: 0.25rem;">{subtitle}</div>' if subtitle else ''}
    </div>
    """, unsafe_allow_html=True)


# Load dataset and precompute optimizations
@st.cache_data
def get_dataset_and_results(file_path: str):
    valid_df, exclusions = load_and_validate_data(file_path)
    
    # Precompute optimization results for all valid sites
    results = []
    for _, row in valid_df.iterrows():
        rec, _ = optimize_site(row)
        monthly_energy = row['Revised Average Load'] * 24.0 * 30.0
        assess = assess_existing_solar(row['PV Capacity (Kw)'], monthly_energy)
        just = get_justification(row, rec, assess)
        
        results.append({
            'No.': row['No.'],
            'Site Name': row['Site Name'],
            'Rectifier Type': row['Rectifier Type'],
            'Rectifier Capacity': row['Rectifier Capacity'],
            'PV Capacity (Kw)': row['PV Capacity (Kw)'],
            'Revised Average Load': row['Revised Average Load'],
            'Monthly Energy (kWh)': monthly_energy,
            'Battery Capacity (AH)': row['Battery Capacity (AH)'],
            'Battery Capacity (kWh)': (row['Battery Capacity (AH)'] * 54.5) / 1000.0,
            '2026 Average Monthly Bill': row['2026 Average Monthly Bill'],
            # Optimized values
            'Recommended Panels Added': rec['panels_added'],
            'Additional Solar Capacity (kWp)': rec['additional_pv_kwp'],
            'Total Recommended Capacity (kWp)': rec['total_pv_kwp'],
            'Rectifier Utilization % (New)': rec['rectifier_utilization'],
            'CAPEX (KES)': rec['capex_kes'],
            'Additional Monthly Savings (KES)': rec['additional_monthly_savings_kes'],
            'Additional Annual Savings (KES)': rec['additional_annual_savings_kes'],
            'ROI %': rec['roi_pct'],
            'Payback Period (Years)': rec['payback_years'],
            'New Monthly Grid Bill (KES)': rec['new_monthly_grid_bill_kes'],
            'Existing Solar Size Status': assess['category'],
            'Justification': just
        })
        
    results_df = pd.DataFrame(results)
    return valid_df, exclusions, results_df


# Load data
DATA_FILE = "Data/Sensitivity Project 2.0.xlsx"
try:
    valid_df, exclusions, results_df = get_dataset_and_results(DATA_FILE)
except Exception as e:
    st.error(f"Error loading the spreadsheet data: {str(e)}")
    st.stop()


# Sidebar Sizing Controls
st.sidebar.markdown(f'# <span class="header-text">Settings</span>', unsafe_allow_html=True)
st.sidebar.markdown("---")

st.sidebar.subheader("Engineering Parameter Reference")
st.sidebar.metric("Electricity Tariff", f"KES {TARIFF_KES:.2f} / kWh")
st.sidebar.metric("Standard Solar Panel", f"{PANEL_RATING_KWP*1000:.0f} Wp ({PANEL_RATING_KWP:.3f} kWp)")
st.sidebar.metric("Installed Cost per Panel", f"KES {INSTALLED_COST_KES:,.2f}")
st.sidebar.metric("Peak Sun Hours (PSH)", f"{5.5} hrs/day")
st.sidebar.metric("System Efficiency", f"{80:.0f}%")

st.sidebar.markdown("---")
st.sidebar.markdown("💡 **Optimization Rule:** The scenario engine adds panels up to the rectifier capacity or until the site energy load is 100% offset, whichever comes first. This maximizes ROI.")


# Header Banner
col1, col2 = st.columns([5, 1])
with col1:
    st.markdown(f'# <span class="header-text">Telecom Solar Sizing Optimizer</span>', unsafe_allow_html=True)
    st.markdown("##### Financially-Driven Solar PV Expansion Strategy & Sizing Platform")
with col2:
    st.image("https://img.icons8.com/color/96/solar-panel.png", width=70)

st.markdown("---")

# Main Application Tabs
tab_overview, tab_ranking, tab_deepdive, tab_rectifier, tab_validation = st.tabs([
    "📊 Portfolio Overview",
    "🏆 Sizing Opportunity Sorter",
    "🔍 Site Deep-Dive",
    "🔌 Rectifier Load Analysis",
    "📋 Data Quality & Exclusions"
])

# -----------------
# TAB 1: PORTFOLIO OVERVIEW
# -----------------
with tab_overview:
    st.markdown("### Portfolio Investment Case")
    
    # Summaries
    total_sites = len(results_df)
    total_capex = results_df['CAPEX (KES)'].sum()
    total_monthly_savings = results_df['Additional Monthly Savings (KES)'].sum()
    total_annual_savings = results_df['Additional Annual Savings (KES)'].sum()
    total_add_capacity = results_df['Additional Solar Capacity (kWp)'].sum()
    
    # Portfolio payback
    portfolio_payback = total_capex / total_annual_savings if total_annual_savings > 0 else 0.0
    
    # Existing vs. Recommended Solar Capacities
    total_existing_solar = results_df['PV Capacity (Kw)'].sum()
    total_new_solar = results_df['Total Recommended Capacity (kWp)'].sum()
    
    # Render Metrics Row
    m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)
    with m_col1:
        render_metric_card("Analyzed Sites", f"{total_sites}", "Successfully validated", "#38bdf8")
    with m_col2:
        render_metric_card("Total Expansion CAPEX", f"KES {total_capex:,.0f}", f"Across {results_df['Recommended Panels Added'].gt(0).sum()} sites", "#818cf8")
    with m_col3:
        render_metric_card("Solar Capacity to Add", f"{total_add_capacity:.2f} kWp", f"Total PV: {total_new_solar:.1f} kWp (+{(total_new_solar/total_existing_solar - 1)*100:.1f}%)", "#a78bfa")
    with m_col4:
        render_metric_card("Annual Grid Bill Savings", f"KES {total_annual_savings:,.0f}", f"KES {total_monthly_savings:,.0f} saved / month", "#10b981")
    with m_col5:
        render_metric_card("Portfolio Payback Period", f"{portfolio_payback:.2f} Years", f"Average ROI: { (total_annual_savings/total_capex)*100 if total_capex > 0 else 0:.1f}%", "#f59e0b")
        
    st.markdown("---")
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.markdown("#### Sizing Assessment of Existing Solar Assets")
        category_counts = results_df['Existing Solar Size Status'].value_counts().reset_index()
        category_counts.columns = ['Status', 'Count']
        
        # Color mapping matching badge colors
        color_map = {
            'Under-sized': '#ef4444',
            'Adequately sized': '#f59e0b',
            'Near optimum': '#10b981',
            'Over-sized': '#8b5cf6'
        }
        
        fig_pie = px.pie(
            category_counts, 
            values='Count', 
            names='Status', 
            color='Status',
            color_discrete_map=color_map,
            hole=0.4
        )
        fig_pie.update_layout(
            template='plotly_dark',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(family='Outfit, sans-serif'),
            legend=dict(orientation="h", y=0, x=0.1)
        )
        st.plotly_chart(fig_pie, use_container_width=True)
        
    with col_chart2:
        st.markdown("#### Cumulative Savings vs Cumulative Investment (Top 25 Sites)")
        # Filter sites with expansion and sort by savings
        top_investments = results_df[results_df['CAPEX (KES)'] > 0].sort_values(by='Additional Annual Savings (KES)', ascending=False).head(25)
        
        top_investments['Cumulative CAPEX'] = top_investments['CAPEX (KES)'].cumsum()
        top_investments['Cumulative Savings'] = top_investments['Additional Annual Savings (KES)'].cumsum()
        
        fig_cum = go.Figure()
        fig_cum.add_trace(go.Scatter(
            x=top_investments['Site Name'],
            y=top_investments['Cumulative Savings'],
            name='Cumulative Annual Savings (KES)',
            mode='lines+markers',
            line=dict(color='#10b981', width=3),
            marker=dict(size=8)
        ))
        fig_cum.add_trace(go.Scatter(
            x=top_investments['Site Name'],
            y=top_investments['Cumulative CAPEX'],
            name='Cumulative CAPEX (KES)',
            mode='lines+markers',
            line=dict(color='#818cf8', width=3, dash='dash'),
            marker=dict(size=8)
        ))
        fig_cum.update_layout(
            template='plotly_dark',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(family='Outfit, sans-serif'),
            xaxis=dict(tickangle=45),
            yaxis=dict(title='KES'),
            legend=dict(orientation="h", y=1.15, x=0.1)
        )
        st.plotly_chart(fig_cum, use_container_width=True)

# -----------------
# TAB 2: OPPORTUNITY RANKING & SORTING
# -----------------
with tab_ranking:
    st.markdown("### Sizing Opportunities Ranker")
    st.markdown("Identify which telecom sites represent the highest potential returns on solar expansion investment.")
    
    # Filtering settings
    rank_col1, rank_col2, rank_col3 = st.columns(3)
    with rank_col1:
        sort_by = st.selectbox(
            "Rank Sites By:",
            ["Highest Annual Savings (KES)", "Best ROI %", "Fastest Payback (Years)", "Highest CAPEX (KES)"]
        )
    with rank_col2:
        rectifier_filter = st.multiselect(
            "Filter Rectifier Type:",
            results_df['Rectifier Type'].unique(),
            default=results_df['Rectifier Type'].unique()
        )
    with rank_col3:
        status_filter = st.multiselect(
            "Filter Existing Solar Status:",
            results_df['Existing Solar Size Status'].unique(),
            default=results_df['Existing Solar Size Status'].unique()
        )
        
    # Apply filters
    filtered_df = results_df[
        results_df['Rectifier Type'].isin(rectifier_filter) &
        results_df['Existing Solar Size Status'].isin(status_filter)
    ]
    
    # Apply sorting
    if sort_by == "Highest Annual Savings (KES)":
        filtered_df = filtered_df.sort_values(by='Additional Annual Savings (KES)', ascending=False)
    elif sort_by == "Best ROI %":
        filtered_df = filtered_df.sort_values(by='ROI %', ascending=False)
    elif sort_by == "Fastest Payback (Years)":
        # Put 0 payback (no addition) at the bottom
        filtered_df['sort_payback'] = filtered_df['Payback Period (Years)'].apply(lambda x: float('inf') if x == 0 else x)
        filtered_df = filtered_df.sort_values(by='sort_payback', ascending=True).drop(columns=['sort_payback'])
    elif sort_by == "Highest CAPEX (KES)":
        filtered_df = filtered_df.sort_values(by='CAPEX (KES)', ascending=False)
        
    # Format Table for Presentation
    display_df = filtered_df[[
        'Site Name', 'Rectifier Type', 'PV Capacity (Kw)', 'Revised Average Load', 
        'Existing Solar Size Status', 'Recommended Panels Added', 'Additional Solar Capacity (kWp)',
        'CAPEX (KES)', 'Additional Monthly Savings (KES)', 'Additional Annual Savings (KES)',
        'ROI %', 'Payback Period (Years)'
    ]].copy()
    
    # Rename columns for clarity
    display_df.columns = [
        'Site Name', 'Rectifier', 'Existing PV (kWp)', 'Avg Load (kW)', 
        'Existing Solar Status', 'Panels Added', 'Add. Solar (kWp)', 
        'CAPEX (KES)', 'Monthly Savings (KES)', 'Annual Savings (KES)', 
        'ROI %', 'Payback (Yrs)'
    ]
    
    # Styling and display
    st.dataframe(
        display_df.style.format({
            'Existing PV (kWp)': '{:.2f}',
            'Avg Load (kW)': '{:.2f}',
            'Add. Solar (kWp)': '{:.2f}',
            'CAPEX (KES)': '{:,.2f}',
            'Monthly Savings (KES)': '{:,.2f}',
            'Annual Savings (KES)': '{:,.2f}',
            'ROI %': '{:.1f}%',
            'Payback (Yrs)': '{:.2f}'
        }),
        use_container_width=True,
        hide_index=True
    )
    
    # Download button
    csv_data = display_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        "📥 Download Sizing Expansion Report (CSV)",
        csv_data,
        "telecom_solar_expansion_recommendations.csv",
        "text/csv",
        key="download-csv"
    )

# -----------------
# TAB 3: SITE DEEP DIVE
# -----------------
with tab_deepdive:
    st.markdown("### Site-Level Sizing Deep Dive")
    
    selected_site = st.selectbox(
        "Search or Select a Telecom Site:",
        results_df['Site Name'].sort_values()
    )
    
    # Get rows
    site_row = valid_df[valid_df['Site Name'] == selected_site].iloc[0]
    site_res = results_df[results_df['Site Name'] == selected_site].iloc[0]
    
    # Get all scenarios
    recommended, scenarios = optimize_site(site_row)
    scenarios_df = pd.DataFrame(scenarios)
    
    # Technical specs columns
    tech_col1, tech_col2 = st.columns([1, 1])
    
    with tech_col1:
        st.markdown("#### Technical & Operational Baseline")
        specs_data = {
            'Parameter': [
                'Site ID / Serial No.',
                'Revised Average Load (kW)',
                'Daily Energy Consumption (kWh/day)',
                'Monthly Energy Consumption (kWh/month)',
                'Rectifier Type Installed',
                'Rectifier Solar Limit (kWp)',
                'Existing PV Capacity (kWp)',
                'Existing Battery Bank Capacity (Ah)',
                'Existing Battery Capacity (kWh)',
                'Baseline Monthly Bill (Calculated)'
            ],
            'Value': [
                f"{site_row['No.']}",
                f"{site_row['Revised Average Load']:.2f} kW",
                f"{site_row['Revised Average Load'] * 24:.2f} kWh/day",
                f"{site_row['Revised Average Load'] * 720:.2f} kWh/month",
                f"{site_row['Rectifier Type']}",
                f"{RECTIFIER_LIMITS[site_row['Rectifier Type']]:.1f} kWp",
                f"{site_row['PV Capacity (Kw)']:.2f} kWp",
                f"{site_row['Battery Capacity (AH)']:.0f} Ah",
                f"{(site_row['Battery Capacity (AH)'] * 54.5)/1000:.2f} kWh (at 54.5V)",
                f"KES {(site_row['Revised Average Load'] * 720 - min(site_row['PV Capacity (Kw)'] * 132, site_row['Revised Average Load'] * 720)) * TARIFF_KES:,.2f}"
            ]
        }
        st.table(pd.DataFrame(specs_data))
        
    with tech_col2:
        st.markdown("#### Existing Asset Sizing Assessment")
        # Display assessment with card style
        assess = assess_existing_solar(site_row['PV Capacity (Kw)'], site_row['Revised Average Load'] * 720)
        
        status_colors = {
            'Under-sized': '#ef4444',
            'Adequately sized': '#f59e0b',
            'Near optimum': '#10b981',
            'Over-sized': '#8b5cf6',
        }
        border_c = status_colors.get(assess['category'], '#818cf8')
        
        st.markdown(f"""
        <div style="
            background-color: rgba(30, 41, 59, 0.4);
            border: 1px solid {border_c};
            border-left: 6px solid {border_c};
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        ">
            <h4 style="margin-top: 0; color: {border_c}; font-family: 'Space Grotesk', sans-serif;">
                Status: {assess['category'].upper()}
            </h4>
            <p style="font-size: 0.95rem; line-height: 1.5; color: #f1f5f9; margin-bottom: 0;">
                {assess['justification']}
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("#### Recommended Expansion Decision")
        rec_panels = site_res['Recommended Panels Added']
        
        if rec_panels > 0:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(6, 95, 70, 0.2) 100%);
                border: 1px solid #10b981;
                border-left: 6px solid #10b981;
                border-radius: 12px;
                padding: 1.5rem;
            ">
                <h4 style="margin-top: 0; color: #10b981; font-family: 'Space Grotesk', sans-serif;">
                    APPROVED INVESTMENT PLAN
                </h4>
                <p style="font-size: 0.95rem; line-height: 1.5; color: #f1f5f9; margin-bottom: 0;">
                    {site_res['Justification']}
                </p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(153, 27, 27, 0.2) 100%);
                border: 1px solid #ef4444;
                border-left: 6px solid #ef4444;
                border-radius: 12px;
                padding: 1.5rem;
            ">
                <h4 style="margin-top: 0; color: #ef4444; font-family: 'Space Grotesk', sans-serif;">
                    EXPANSION NOT VIABLE
                </h4>
                <p style="font-size: 0.95rem; line-height: 1.5; color: #f1f5f9; margin-bottom: 0;">
                    {site_res['Justification']}
                </p>
            </div>
            """, unsafe_allow_html=True)
            
    st.markdown("---")
    
    # Charts for Deep Dive
    st.markdown("#### Expansion Scenario Evaluation Engine")
    
    col_chart_sd1, col_chart_sd2 = st.columns(2)
    
    with col_chart_sd1:
        # Dual axis chart: CAPEX vs Annual Savings
        fig_sd_cum = make_subplots(specs=[[{"secondary_y": True}]])
        
        fig_sd_cum.add_trace(go.Bar(
            x=scenarios_df['panels_added'],
            y=scenarios_df['capex_kes'],
            name='Project CAPEX (KES)',
            marker_color='#818cf8',
            opacity=0.8
        ), secondary_y=False)
        
        fig_sd_cum.add_trace(go.Scatter(
            x=scenarios_df['panels_added'],
            y=scenarios_df['additional_annual_savings_kes'],
            name='Additional Annual Savings (KES)',
            mode='lines+markers',
            line=dict(color='#10b981', width=3),
            marker=dict(size=8)
        ), secondary_y=True)
        
        # Add recommended line indicator
        fig_sd_cum.add_vline(x=recommended['panels_added'], line_width=2, line_dash="dash", line_color="#ef4444")
        
        fig_sd_cum.update_layout(
            title=f"Sizing Curve: CAPEX vs. Savings for {selected_site}",
            template='plotly_dark',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(family='Outfit, sans-serif'),
            xaxis=dict(title='Number of Panels Added'),
            legend=dict(orientation="h", y=1.15, x=0.1)
        )
        fig_sd_cum.update_yaxes(title_text="CAPEX (KES)", secondary_y=False)
        fig_sd_cum.update_yaxes(title_text="Annual Savings (KES)", secondary_y=True)
        st.plotly_chart(fig_sd_cum, use_container_width=True)
        st.info("💡 **Observation:** Notice the inflection point. Once solar generation equals the site consumption load, additional panels result in KES 0 additional savings, causing the ROI to drop.")
        
    with col_chart_sd2:
        # ROI and Payback chart
        # Filter out 0 panels scenario to avoid inf/0 division in payback visualization
        scenarios_filtered = scenarios_df[scenarios_df['panels_added'] > 0]
        
        fig_sd_metrics = make_subplots(specs=[[{"secondary_y": True}]])
        
        fig_sd_metrics.add_trace(go.Scatter(
            x=scenarios_filtered['panels_added'],
            y=scenarios_filtered['roi_pct'],
            name='Expansion ROI (%)',
            mode='lines+markers',
            line=dict(color='#c084fc', width=3),
            marker=dict(size=8)
        ), secondary_y=False)
        
        fig_sd_metrics.add_trace(go.Scatter(
            x=scenarios_filtered['panels_added'],
            y=scenarios_filtered['payback_years'],
            name='Expansion Payback (Years)',
            mode='lines+markers',
            line=dict(color='#f59e0b', width=3),
            marker=dict(size=8)
        ), secondary_y=True)
        
        fig_sd_metrics.add_vline(x=recommended['panels_added'], line_width=2, line_dash="dash", line_color="#ef4444")
        
        fig_sd_metrics.update_layout(
            title=f"Financial Returns: ROI & Payback vs. Panels Added for {selected_site}",
            template='plotly_dark',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(family='Outfit, sans-serif'),
            xaxis=dict(title='Number of Panels Added'),
            legend=dict(orientation="h", y=1.15, x=0.1)
        )
        fig_sd_metrics.update_yaxes(title_text="ROI (%)", secondary_y=False)
        fig_sd_metrics.update_yaxes(title_text="Payback Period (Years)", secondary_y=True)
        st.plotly_chart(fig_sd_metrics, use_container_width=True)
        
    # Show full scenario table for transparency
    st.markdown("#### Scenario Calculation Ledger")
    st.markdown("All financial calculations are transparent and auditable below:")
    
    tbl_df = scenarios_df[[
        'panels_added', 'additional_pv_kwp', 'total_pv_kwp', 'rectifier_utilization',
        'monthly_solar_production_kwh', 'solar_contribution_pct', 'capex_kes',
        'additional_monthly_savings_kes', 'additional_annual_savings_kes',
        'roi_pct', 'payback_years', 'new_monthly_grid_bill_kes'
    ]].copy()
    
    tbl_df.columns = [
        'Panels Added', 'Add. PV (kWp)', 'Total PV (kWp)', 'Rectifier Util. %',
        'Solar Gen (kWh/mo)', 'Solar Cont. %', 'CAPEX (KES)',
        'Monthly Savings (KES)', 'Annual Savings (KES)',
        'ROI %', 'Payback (Years)', 'New Grid Bill (KES)'
    ]
    
    st.dataframe(
        tbl_df.style.format({
            'Add. PV (kWp)': '{:.3f}',
            'Total PV (kWp)': '{:.3f}',
            'Rectifier Util. %': '{:.1f}%',
            'Solar Gen (kWh/mo)': '{:,.1f}',
            'Solar Cont. %': '{:.1f}%',
            'CAPEX (KES)': '{:,.2f}',
            'Monthly Savings (KES)': '{:,.2f}',
            'Annual Savings (KES)': '{:,.2f}',
            'ROI %': '{:.1f}%',
            'Payback (Years)': '{:.2f}',
            'New Grid Bill (KES)': '{:,.2f}'
        }),
        use_container_width=True,
        hide_index=True
    )

# -----------------
# TAB 4: RECTIFIER INFRASTRUCTURE ANALYSIS
# -----------------
with tab_rectifier:
    st.markdown("### Rectifier Capacity & Headroom Load Analysis")
    st.markdown("Assess remaining rectifier headroom and how capacity is utilized across rectifier models before and after solar expansion.")
    
    # Calculate average utilization by rectifier type
    rect_summary = results_df.groupby('Rectifier Type').agg(
        total_sites=('Site Name', 'count'),
        avg_limit=('Rectifier Capacity', 'mean'),
        avg_exist_pv=('PV Capacity (Kw)', 'mean'),
        avg_rec_pv=('Total Recommended Capacity (kWp)', 'mean')
    ).reset_index()
    
    rect_summary['Existing Util %'] = (rect_summary['avg_exist_pv'] / rect_summary['avg_limit']) * 100.0
    rect_summary['Recommended Util %'] = (rect_summary['avg_rec_pv'] / rect_summary['avg_limit']) * 100.0
    rect_summary['Available Headroom (kWp)'] = rect_summary['avg_limit'] - rect_summary['avg_rec_pv']
    
    col_rect1, col_rect2 = st.columns([2, 1])
    
    with col_rect1:
        st.markdown("#### Rectifier Solar Capacity Sizing Summary")
        st.dataframe(
            rect_summary.style.format({
                'avg_limit': '{:.1f} kWp',
                'avg_exist_pv': '{:.2f} kWp',
                'avg_rec_pv': '{:.2f} kWp',
                'Existing Util %': '{:.1f}%',
                'Recommended Util %': '{:.1f}%',
                'Available Headroom (kWp)': '{:.2f} kWp'
            }),
            use_container_width=True,
            hide_index=True
        )
        
    with col_rect2:
        st.markdown("#### Remaining Headroom Capacity")
        for idx, r_row in rect_summary.iterrows():
            st.metric(
                f"{r_row['Rectifier Type']} Safe Margin",
                f"{r_row['Available Headroom (kWp)']:.2f} kWp",
                f"Final Util: {r_row['Recommended Util %']:.1f}%"
            )
            
    st.markdown("---")
    
    # Chart showing Rectifier Capacity utilization
    st.markdown("#### Visual Sizing: Before vs. After Sizing Optimization")
    
    fig_rect_util = go.Figure()
    fig_rect_util.add_trace(go.Bar(
        x=rect_summary['Rectifier Type'],
        y=rect_summary['Existing Util %'],
        name='Existing Rectifier Utilization (%)',
        marker_color='#ef4444',
        opacity=0.8
    ))
    fig_rect_util.add_trace(go.Bar(
        x=rect_summary['Rectifier Type'],
        y=rect_summary['Recommended Util %'],
        name='Recommended Rectifier Utilization (%)',
        marker_color='#10b981',
        opacity=0.8
    ))
    fig_rect_util.update_layout(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Outfit, sans-serif'),
        yaxis=dict(title='Utilization % (Max 100%)', range=[0, 100]),
        legend=dict(orientation="h", y=1.15, x=0.1)
    )
    st.plotly_chart(fig_rect_util, use_container_width=True)

# -----------------
# TAB 5: DATA QUALITY & EXCLUSIONS
# -----------------
with tab_validation:
    st.markdown("### Data Quality & Integrity Report")
    st.markdown("Examine the results of the automated data validation check. All processed rows and exclusions are reported here.")
    
    val_col1, val_col2 = st.columns(2)
    with val_col1:
        render_metric_card("Total Sites Evaluated", f"{len(valid_df) + len(exclusions)}", "Combined dataset size", "#38bdf8")
    with val_col2:
        render_metric_card("Excluded Sites", f"{len(exclusions)}", "Failed quality checks", "#ef4444" if len(exclusions) > 0 else "#10b981")
        
    st.markdown("---")
    
    if len(exclusions) > 0:
        st.markdown("#### Excluded Sites Ledger")
        st.markdown("The following sites were excluded from the solar optimization engine because of data quality errors. Each row lists a specific reason.")
        
        ex_df = pd.DataFrame(exclusions)
        # Reorder columns for presentation
        ex_display = ex_df[[
            'No.', 'Site Name', 'Rectifier Type', 'Rectifier Capacity', 
            'PV Capacity (Kw)', '2026 Average Monthly Bill', 'Revised Average Load', 'Reason'
        ]]
        ex_display.columns = [
            'No.', 'Site Name', 'Rectifier Type', 'Rectifier Cap (kWp)', 
            'Exist PV (kWp)', 'Monthly Bill (KES)', 'Revised Load (kW)', 'Exclusion Reason'
        ]
        
        st.dataframe(ex_display, use_container_width=True, hide_index=True)
    else:
        st.success("🎉 Excellent! All sites in the dataset passed 100% of the validation and quality checks. Zero sites were excluded.")
