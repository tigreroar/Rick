import streamlit as st
import pandas as pd
import google.generativeai as genai
import os
import pdfplumber
from fpdf import FPDF
from duckduckgo_search import DDGS
from datetime import date

# --- CONFIGURATION ---
st.set_page_config(page_title="Listing Powerhouse AI (Rick Mode)", page_icon="🏠", layout="wide")

# --- 1. INTERNET SEARCH (IMPROVED) ---
def get_web_estimates(address):
    """Searches specifically for Zestimates to avoid 'No data found'."""
    # We ask specifically for 'price' and 'zestimate'
    search_query = f"{address} zillow redfin price estimate"
    results_text = ""
    try:
        # backend='api' sometimes works better for bots
        with DDGS() as ddgs:
            results = list(ddgs.text(search_query, max_results=5))
            for r in results:
                results_text += f"- Source: {r['title']}\n  Snippet: {r['body']}\n\n"
        
        if not results_text:
            return "WARNING: Automated search was blocked or empty. Assume Zillow has data but we couldn't fetch it."
        return results_text
    except Exception as e:
        return f"Search Error (Likely IP Blocked): {e}"

# --- 2. PDF GENERATION ---
class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Listing Powerhouse Strategy Report', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 12)
        self.set_fill_color(200, 220, 255)
        self.cell(0, 10, title, 0, 1, 'L', 1)
        self.ln(4)

def create_pdf(content, agent_name, address, metrics, web_summary):
    pdf = PDFReport()
    pdf.add_page()
    
    # COVER
    pdf.set_font('Arial', 'B', 24)
    pdf.ln(40)
    pdf.cell(0, 10, "Strategic Listing Plan", 0, 1, 'C')
    pdf.set_font('Arial', '', 16)
    pdf.cell(0, 10, f"{address}", 0, 1, 'C')
    pdf.ln(10)
    pdf.set_font('Arial', 'I', 12)
    pdf.cell(0, 10, f"Date: {date.today().strftime('%B %d, %Y')}", 0, 1, 'C') # FECHA REAL
    pdf.ln(10)
    pdf.set_font('Arial', 'I', 14)
    pdf.cell(0, 10, f"Prepared by: {agent_name}", 0, 1, 'C')
    
    # METRICS
    pdf.add_page()
    pdf.chapter_title("Market Intelligence")
    pdf.set_font('Arial', '', 11)
    
    if isinstance(metrics, dict):
        pdf.cell(0, 10, f"Absorption Rate (MOI): {metrics['months_inventory']} Months", 0, 1)
        pdf.cell(0, 10, f"Success Probability: {metrics['success_ratio']}%", 0, 1)
        # Mostramos el precio del sujeto si existe, si no el promedio
        if metrics.get('subject_price') and metrics['subject_price'] != "N/A":
             pdf.cell(0, 10, f"Subject Property List Price (CSV): {metrics['subject_price']}", 0, 1)
        else:
             pdf.cell(0, 10, f"Avg Neighborhood Price: {metrics['avg_sold_price']}", 0, 1)
    
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 10, "Online Intelligence (Zillow/Redfin):", 0, 1)
    pdf.set_font('Arial', '', 10)
    
    clean_web = web_summary.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 6, clean_web)
    pdf.ln(10)
    
    # CONTENT
    pdf.chapter_title("Strategic Execution")
    pdf.set_font('Arial', '', 11)
    
    lines = content.split('\n')
    for line in lines:
        clean_line = line.encode('latin-1', 'replace').decode('latin-1')
        if line.startswith('###') or line.startswith('**'):
            pdf.set_font('Arial', 'B', 11)
            pdf.multi_cell(0, 8, clean_line.replace('*', '').replace('#', ''))
            pdf.set_font('Arial', '', 11)
        else:
            pdf.multi_cell(0, 6, clean_line.replace('*', ''))
            
    return pdf.output(dest='S').encode('latin-1')

# --- 3. DATA LOGIC (RICK'S LOGIC) ---
def load_knowledge_base():
    text = ""
    path = "knowledge_base"
    if not os.path.exists(path): return ""
    for f in os.listdir(path):
        try:
            fp = os.path.join(path, f)
            if f.lower().endswith('.pdf'):
                with pdfplumber.open(fp) as pdf:
                    for p in pdf.pages:
                        extracted = p.extract_text()
                        if extracted: text += extracted + "\n"
            elif f.lower().endswith(('.txt', '.md')):
                with open(fp, 'r', encoding='utf-8') as file: text += file.read()
        except: pass
    return text

def calculate_metrics(df, months=6, subject_address=""):
    """
    Calculates metrics AND searches for the subject property in the CSV
    to find the REAL target price (e.g., $870k) instead of the average ($1M).
    """
    try:
        df.columns = [c.lower().strip() for c in df.columns]
        
        # 1. Identify Columns
        status_col = next((c for c in df.columns if 'status' in c), None)
        if not status_col: return "ERROR: 'Status' column missing."

        excluded_words = ['date', 'agent', 'office', 'code', 'phone', 'zip', 'id']
        possible_price_cols = [c for c in df.columns if ('price' in c or 'list' in c or 'sold' in c) and not any(x in c for x in excluded_words)]
        price_col = next((c for c in possible_price_cols if 'sold' in c or 'closed' in c), possible_price_cols[0] if possible_price_cols else None)
        
        # 2. Find Subject Property Price (The "Rick" Fix)
        subject_price_found = "N/A"
        if subject_address:
            # Simple fuzzy search: check if address part exists in any column
            # We assume user inputs "123 Main". We look for that string in the dataframe.
            mask = df.apply(lambda row: row.astype(str).str.contains(subject_address, case=False).any(), axis=1)
            subject_row = df[mask]
            
            if not subject_row.empty and price_col:
                # Get the value from the first match
                raw_val = str(subject_row.iloc[0][price_col])
                subject_price_found = raw_val # e.g. "$870,000"

        # 3. Market Stats
        status_series = df[status_col].astype(str)
        sold = df[status_series.str.contains('sold|closed', case=False, na=False)].shape[0]
        active = df[status_series.str.contains('active|avail', case=False, na=False)].shape[0]
        # Rick's Formula: Expired + Withdrawn + Canceled
        failed = df[status_series.str.contains('exp|with|canc|term', case=False, na=False)].shape[0]
        
        sales_pm = sold / months
        moi = (active / sales_pm) if sales_pm > 0 else 99.9
        attempts = sold + failed
        success = (sold / attempts * 100) if attempts > 0 else 0
        
        # 4. Average Price
        avg_price = 0
        if price_col:
            clean_prices = df[status_series.str.contains('sold|closed', case=False, na=False)][price_col].astype(str).str.replace(r'[$,]', '', regex=True)
            avg_price = pd.to_numeric(clean_prices, errors='coerce').mean()

        return {
            "months_inventory": round(moi, 2),
            "success_ratio": round(success, 1),
            "avg_sold_price": f"${avg_price:,.0f}" if avg_price > 0 else "N/A",
            "failed": failed,
            "subject_price": subject_price_found # This is the Key for Rick's accuracy
        }
    except Exception as e:
        return f"Calc Error: {str(e)}"

# --- 4. INTERFACE ---
with st.sidebar:
    st.header("⚙️ Settings")
    env_key = os.getenv("GOOGLE_API_KEY")
    api_key = env_key if env_key else st.text_input("🔑 API Key", type="password")
    st.divider()
    agent_name = st.text_input("Agent Name", value="Fernando Herboso")
    uploaded_file = st.file_uploader("Upload MLS CSV", type=["csv"])
    months_analyzed = st.number_input("Months Analyzed", value=6)

st.title("🏠 Listing Powerhouse AI")
st.markdown("### The 'Rick' Logic Generator")

col1, col2 = st.columns([3, 1])
with col1:
    # Important: User must type the address part that matches the CSV (e.g. "9012" or "Goshen")
    address = st.text_input("📍 Subject Property Address (Matches CSV):", placeholder="e.g. 123 Main St")

if st.button("🚀 Run Analysis"):
    if not api_key or not address or not uploaded_file:
        st.error("Missing Data.")
    else:
        # 1. Process CSV & Find Subject Price
        df = pd.read_csv(uploaded_file)
        # Pass address to find the specific $870k price
        metrics = calculate_metrics(df, months_analyzed, address)
        
        if isinstance(metrics, str):
            st.error(metrics)
            st.stop()

        # 2. Web Search
        with st.spinner('🌍 Searching Zillow/Redfin...'):
            web_raw_data = get_web_estimates(address)

        # 3. Knowledge
        kb_text = load_knowledge_base()

        # 4. PROMPT (The "Rick" Persona)
        prompt = f"""
        ACT AS: Real Estate Analyst 'Rick' for agent {agent_name}.
        DATE: {date.today().strftime('%B %d, %Y')}
        TARGET PROPERTY: {address}
        
        === DATA INTELLIGENCE ===
        1. MARKET REALITY (CSV):
           - MOI: {metrics['months_inventory']} Months (Speed of market)
           - Success Ratio: {metrics['success_ratio']}% (Prob of selling)
           - Failed Listings: {metrics['failed']} (Risk)
           
        2. PRICING ANCHOR:
           - Subject Property Current/List Price in CSV: {metrics['subject_price']}
           - Neighborhood Avg: {metrics['avg_sold_price']}
           (CRITICAL: If the 'Subject Property Price' is found (e.g. $870k), use THAT as the target 'Sweet Spot'. Do NOT use the neighborhood average if it's way higher.)

        3. ONLINE "NOISE" (Web Search):
           {web_raw_data}
           (Instruction: If you see Zestimates higher than the Subject Price, label them as "Algo-Noise" and use the Zillow CEO script. If web search failed, admit it but assume Zillow is likely inaccurate.)

        === KNOWLEDGE BASE ===
        {kb_text[:15000]}
        
        === TASK ===
        Write a Strategic Report.
        - **Pricing:** Validate the price of {metrics['subject_price']} (if available) as the "Sweet Spot". Explain why $1M (Avg) is wrong if the subject is $870k.
        - **Success:** Explain that {metrics['success_ratio']}% means ~3 out of 10 homes FAIL.
        - **Date:** Use today's date.
        """

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        with st.spinner('Thinking like Rick...'):
            try:
                response = model.generate_content(prompt)
                report_text = response.text
                
                web_summary = model.generate_content(f"Summarize price estimates from: {web_raw_data}").text
                
                # Display
                m1, m2, m3 = st.columns(3)
                m1.metric("Target Price (CSV)", metrics['subject_price'])
                m2.metric("Success Ratio", f"{metrics['success_ratio']}%")
                m3.metric("Inventory", f"{metrics['months_inventory']} Mo")
                
                st.markdown(report_text)
                
                pdf_bytes = create_pdf(report_text, agent_name, address, metrics, web_summary)
                st.download_button("📥 Download Report", pdf_bytes, f"Rick_Report_{address}.pdf", "application/pdf")
                
            except Exception as e:
                st.error(f"Error: {e}")

