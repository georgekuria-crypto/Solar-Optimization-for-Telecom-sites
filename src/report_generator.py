from fpdf import FPDF
import pandas as pd
from datetime import datetime

class ExecutiveReport(FPDF):
    def header(self):
        # Logo placeholder or Title
        self.set_font('Helvetica', 'B', 20)
        self.set_text_color(11, 15, 25) # Dark navy
        self.cell(0, 10, 'Telecom Solar Expansion', border=0, ln=1, align='C')
        
        self.set_font('Helvetica', '', 14)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, 'Executive Summary & Investment Case', border=0, ln=1, align='C')
        self.ln(5)
        
    def footer(self):
        # Position at 1.5 cm from bottom
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        # Page number
        self.cell(0, 10, f'Page {self.page_no()} | Generated on {datetime.now().strftime("%Y-%m-%d %H:%M")}', align='C')

def generate_executive_pdf(results_df: pd.DataFrame) -> bytes:
    """
    Generates a PDF executive summary report from the optimization results.
    Returns the PDF as a byte string.
    """
    pdf = ExecutiveReport()
    pdf.add_page()
    
    # Calculate portfolio aggregates
    total_sites = len(results_df)
    sites_with_expansion = int(results_df['Panels to Add'].gt(0).sum())
    total_panels = int(results_df['Panels to Add'].sum())
    
    total_capex = results_df['CAPEX (KES)'].sum()
    total_annual_sav = results_df['Annual Savings (KES)'].sum()
    total_monthly_sav = results_df['Monthly Savings (KES)'].sum()
    
    portfolio_payback = total_capex / total_annual_sav if total_annual_sav > 0 else 0.0
    portfolio_roi = (total_annual_sav / total_capex * 100) if total_capex > 0 else 0.0
    
    total_add_pv = results_df['Additional Solar (kWp)'].sum()
    
    # ── Section 1: Portfolio Overview ─────────────────────────────────────────
    pdf.set_font('Helvetica', 'B', 16)
    pdf.set_text_color(11, 15, 25)
    pdf.cell(0, 10, '1. Portfolio Investment Case', ln=1)
    
    pdf.set_font('Helvetica', '', 11)
    pdf.set_text_color(50, 50, 50)
    summary_text = (
        f"Out of {total_sites} validated telecom sites, {sites_with_expansion} sites have been "
        f"identified as financially viable for solar PV expansion. "
        f"The proposed strategy recommends installing a total of {total_panels} new solar panels "
        f"(+{total_add_pv:.1f} kWp) across these sites."
    )
    pdf.multi_cell(0, 6, summary_text)
    pdf.ln(5)
    
    # Metrics Table
    pdf.set_fill_color(240, 245, 255)
    pdf.set_font('Helvetica', 'B', 11)
    
    # Table Header
    pdf.cell(95, 10, 'Financial Metric', border=1, align='C', fill=True)
    pdf.cell(95, 10, 'Value', border=1, align='C', fill=True)
    pdf.ln()
    
    pdf.set_font('Helvetica', '', 11)
    
    metrics = [
        ("Total Project CAPEX", f"KES {total_capex:,.0f}"),
        ("Annual Grid Bill Savings", f"KES {total_annual_sav:,.0f} / year"),
        ("Monthly Grid Bill Savings", f"KES {total_monthly_sav:,.0f} / month"),
        ("Portfolio Return on Investment (ROI)", f"{portfolio_roi:.1f}%"),
        ("Portfolio Payback Period", f"{portfolio_payback:.2f} Years")
    ]
    
    for label, value in metrics:
        pdf.cell(95, 10, label, border=1)
        pdf.cell(95, 10, value, border=1, align='R')
        pdf.ln()
        
    pdf.ln(10)
    
    # ── Section 2: Top 10 Recommended Sites ──────────────────────────────────
    pdf.set_font('Helvetica', 'B', 16)
    pdf.set_text_color(11, 15, 25)
    pdf.cell(0, 10, '2. Top 10 Sites by Annual Savings', ln=1)
    
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(50, 50, 50)
    pdf.multi_cell(0, 6, "The following table highlights the top 10 telecom sites that represent the highest potential returns and largest absolute savings from solar expansion.")
    pdf.ln(4)
    
    top10 = results_df[results_df['CAPEX (KES)'] > 0].nlargest(10, 'Annual Savings (KES)')
    
    if len(top10) > 0:
        # Table Header
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_fill_color(220, 230, 245)
        
        col_widths = [40, 30, 20, 35, 35, 30]
        headers = ['Site Name', 'Rectifier', 'Panels', 'CAPEX (KES)', 'Annual Sav. (KES)', 'Payback (Yrs)']
        
        for i, header in enumerate(headers):
            pdf.cell(col_widths[i], 8, header, border=1, align='C', fill=True)
        pdf.ln()
        
        # Table Body
        pdf.set_font('Helvetica', '', 9)
        for _, row in top10.iterrows():
            pdf.cell(col_widths[0], 8, str(row['Site Name'])[:20], border=1)
            pdf.cell(col_widths[1], 8, str(row['Rectifier Type'])[:15], border=1, align='C')
            pdf.cell(col_widths[2], 8, str(int(row['Panels to Add'])), border=1, align='C')
            pdf.cell(col_widths[3], 8, f"{row['CAPEX (KES)']:,.0f}", border=1, align='R')
            pdf.cell(col_widths[4], 8, f"{row['Annual Savings (KES)']:,.0f}", border=1, align='R')
            pdf.cell(col_widths[5], 8, f"{row['Payback Period (Years)']:.2f}", border=1, align='C')
            pdf.ln()
    else:
        pdf.cell(0, 10, "No sites require expansion based on the current data.", border=0)
        
    return bytes(pdf.output())
