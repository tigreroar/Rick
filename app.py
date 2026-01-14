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
    search_query = f"{address} price estimate zillow redfin realtor"
    results_text = ""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(search_query, max_results=5))
            for r in results:
                results_text += f"- Source: {r['title']}\n  Snippet: {r['body']}\n\n"
        
        if not results_text:
            return "WARNING: Automated search blocked. Assume Zestimate is likely higher than market value."
        return results_text
    except Exception as e:
        return f"Search Error: {e}"

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
    pdf.cell(0, 10, f"Date: {date.today().strftime('%B %d, %Y')}", 0, 1, 'C')
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
        
        # LOGICA RICK: Mostrar el precio ESPECIFICO si existe
        if metrics.get('subject_price') and metrics['subject_price'] != "N/A":
             pdf.set_font('Arial', 'B', 11)
             pdf.cell(0, 10, f"TARGET LIST PRICE (Sweet Spot): {metrics['subject_price']}", 0, 1)
             pdf.set_font('Arial', '', 11)
             pdf.cell(0, 10, f"(Neighborhood Avg: {metrics['avg_sold_price']})", 0, 1)
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

# --- 3. DATA LOGIC (SMART SEARCH FIX) ---
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
    Calculates metrics and INTELLIGENTLY finds the subject property 
    by combining StreetNumber + StreetName columns.
    """
    try:
        df.columns = [c.lower().strip() for c in df.columns]
        
        # 1. Identify Columns
        status_col = next((c for c in df.columns if 'status' in c), None)
        if not status_col: return "ERROR: 'Status' column missing."

        excluded_words = ['date', 'agent', 'office', 'code', 'phone', 'zip', 'id']
        possible_price_cols = [c for c in df.columns if ('price' in c or 'list' in c or 'sold' in c) and not any(x in c for x in excluded_words)]
        price_col = next((c for c in possible_price_cols if 'sold' in c or 'closed' in c), possible_price_cols[0] if possible_price_cols else None)
        
        # 2. SMART FIND SUBJECT PROPERTY (THE FIX)
        subject_price_found = "N/A"
        
        # Check if we have split address columns (StreetNumber, StreetName)
        st_num_col = next((c for c in df.columns if 'streetnumber' in c or 'stnum' in c), None)
        st_name_col = next((c for c in df.columns if 'streetname' in c or 'stname' in c), None)
        
        if subject_address and st_num_col and st_name_col:
            # Create a temporary 'FullAddress' column for searching
            df['temp_full_address'] = df[st_num_col].astype(str) + " " + df[st_name_col].astype(str)
            
            # Extract just the street part from user input (e.g., "9012 Goshen" from "9012 Goshen Valley Dr...")
            # We assume the first few words are the most important
            search_term = " ".join(subject_address.split()[:2]) # "9012 Goshen"
            
            # Find match
            mask = df['temp_full_address'].str.contains(search_term, case=False, na=False)
            subject_row = df[mask]
            
            if not subject_row.empty and price_col:
                # Get the value from the first match
                raw_val = str(subject_row.iloc[0][price_col])
                subject_price_found = raw_val # e.g. "$870,000"

        # 3. Market Stats
        status_series = df[status_col].astype(str)
        sold = df[status_series.str.contains('sold|closed', case=False, na=False)].shape[0]
        active = df[status_series.str.contains('active|avail', case=False, na=False)].shape[0]
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
            "subject_price": subject_price_found 
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
st.markdown("### Strategic Real Estate Analyst")

col1, col2 = st.columns([3, 1])
with col1:
    # Instruction for better matching
    address = st.text_input("📍 Subject Property Address:", placeholder="e.g. 9012 Goshen Valley")

if st.button("🚀 Run Analysis"):
    if not api_key or not address or not uploaded_file:
        st.error("Missing Data.")
    else:
        # 1. Process CSV
        df = pd.read_csv(uploaded_file)
        metrics = calculate_metrics(df, months_analyzed, address)
        
        if isinstance(metrics, str):
            st.error(metrics)
            st.stop()
            
        # Check if Subject Price was found
        if metrics['subject_price'] == "N/A":
             st.warning(f"⚠️ Could not find '{address}' in the CSV. Using Neighborhood Average (${metrics['avg_sold_price']}). Try typing just the street number and name (e.g., '9012 Goshen').")
        else:
             st.success(f"✅ FOUND Subject Property in CSV! Target Price: {metrics['subject_price']}")

        # 2. Web Search
        with st.spinner('🌍 Searching Zillow/Redfin...'):
            web_raw_data = get_web_estimates(address)

        # 3. Knowledge
        kb_text = load_knowledge_base()

        # 4. PROMPT (RICK PERSONA)
        prompt = f"""
        ACT AS: Real Estate Analyst 'Rick'.
        DATE: {date.today().strftime('%B %d, %Y')}
        TARGET PROPERTY: {address}
        
        === DATA INTELLIGENCE ===
        1. MARKET REALITY (CSV):
           - MOI: {metrics['months_inventory']} Months
           - Success Ratio: {metrics['success_ratio']}%
           - Failed Listings: {metrics['failed']}
           
        2. PRICING ANCHOR (CRITICAL):
           - Subject Property List Price (from CSV): {metrics['subject_price']}
           - Neighborhood Avg: {metrics['avg_sold_price']}
           
           INSTRUCTION: If 'Subject Property List Price' is available (e.g. $870k), YOU MUST USE IT as the "Agent's Sweet Spot" or "Target Price". 
           Ignore the Neighborhood Avg ($1M+) as it is misleading.
           
        3. ONLINE ESTIMATES (Web Search):
           {web_raw_data}
           INSTRUCTION: If Zillow/Redfin show prices HIGHER than the CSV List Price ({metrics['subject_price']}), label them as "Inflated Algorithms".
           Use the CEO of Zillow script to discredit them.

        === KNOWLEDGE BASE ===
        {kb_text[:15000]}
        
        === TASK ===
        Write a Strategic Report.
        - **Pricing Section:** Explicitly state the Agent's Recommended Price is {metrics['subject_price']} (if found). Explain why.
        - **AVM Critique:** Compare the {metrics['subject_price']} vs Zillow's numbers.
        """

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        with st.spinner('Calculating Strategy...'):
            try:
                response = model.generate_content(prompt)
                report_text = response.text
                
                web_summary = model.generate_content(f"Summarize price estimates from: {web_raw_data}").text
                
                # Display
                m1, m2, m3 = st.columns(3)
                m1.metric("Target Price (Rick's Pick)", metrics['subject_price'])
                m2.metric("Success Ratio", f"{metrics['success_ratio']}%")
                m3.metric("Inventory", f"{metrics['months_inventory']} Mo")
                
                st.markdown(report_text)
                
                pdf_bytes = create_pdf(report_text, agent_name, address, metrics, web_summary)
                st.download_button("📥 Download Report", pdf_bytes, f"Rick_Report_{address}.pdf", "application/pdf")
                
            except Exception as e:
                st.error(f"Error: {e}")


