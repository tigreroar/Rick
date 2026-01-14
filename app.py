import streamlit as st
import pandas as pd
import google.generativeai as genai
import os
import pdfplumber
from fpdf import FPDF
from duckduckgo_search import DDGS

# --- CONFIGURATION ---
st.set_page_config(page_title="Listing Powerhouse AI", page_icon="🏠", layout="wide")

# --- 1. INTERNET SEARCH (DUCKDUCKGO) ---
def get_web_estimates(address):
    """Searches for Zillow/Redfin price estimates."""
    search_query = f"{address} price estimate zillow redfin realtor"
    results_text = ""
    try:
        with DDGS() as ddgs:
            # We fetch 4 results
            results = list(ddgs.text(search_query, max_results=4))
            for r in results:
                results_text += f"- Source: {r['title']}\n  Snippet: {r['body']}\n\n"
        
        if not results_text:
            return "No online estimates found."
        return results_text
    except Exception as e:
        return f"Internet Search Error: {e}"

# --- 2. PDF GENERATION ENGINE ---
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
        self.set_fill_color(200, 220, 255) # Light Blue
        self.cell(0, 10, title, 0, 1, 'L', 1)
        self.ln(4)

def create_pdf(content, agent_name, address, metrics, web_summary):
    pdf = PDFReport()
    pdf.add_page()
    
    # --- COVER PAGE ---
    pdf.set_font('Arial', 'B', 24)
    pdf.ln(40)
    pdf.cell(0, 10, "Strategic Listing Plan", 0, 1, 'C')
    pdf.set_font('Arial', '', 16)
    pdf.cell(0, 10, f"Property: {address}", 0, 1, 'C')
    pdf.ln(20)
    pdf.set_font('Arial', 'I', 14)
    pdf.cell(0, 10, f"Prepared by: {agent_name}", 0, 1, 'C')
    
    # --- METRICS PAGE ---
    pdf.add_page()
    pdf.chapter_title("Market Reality Check")
    pdf.set_font('Arial', '', 11)
    
    if isinstance(metrics, dict):
        pdf.cell(0, 10, f"Absorption Rate (MOI): {metrics['months_inventory']} Months", 0, 1)
        pdf.cell(0, 10, f"Probability of Sale: {metrics['success_ratio']}%", 0, 1)
        pdf.cell(0, 10, f"Avg Sold Price (Neighborhood): {metrics['avg_sold_price']}", 0, 1)
    
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 10, "Online Intelligence (Zillow/Redfin):", 0, 1)
    pdf.set_font('Arial', '', 10)
    
    # Clean web summary for PDF
    clean_web = web_summary.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 6, clean_web)
    pdf.ln(10)
    
    # --- STRATEGY PAGE ---
    pdf.chapter_title("Strategic Execution")
    pdf.set_font('Arial', '', 11)
    
    # Process markdown text to plain text
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

# --- 3. DATA LOGIC (ROBUST) ---
def load_knowledge_base():
    """Reads PDF/TXT files from 'knowledge_base' folder."""
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

def calculate_metrics(df, months=6):
    """
    Calculates market metrics handling messy CSVs.
    Fixes the 'ListDate' vs 'ListPrice' confusion.
    """
    try:
        # Normalize columns to lowercase
        df.columns = [c.lower().strip() for c in df.columns]
        
        # A. Find STATUS column
        status_col = next((c for c in df.columns if 'status' in c), None)
        if not status_col: 
            return "ERROR: Could not find a 'Status' column in the CSV."

        # B. Find PRICE column (Smart Filter)
        # We exclude columns that contain 'date', 'agent', 'office', 'code' to avoid picking the wrong one
        excluded_words = ['date', 'agent', 'office', 'code', 'phone', 'zip', 'id']
        possible_price_cols = [
            c for c in df.columns 
            if ('price' in c or 'list' in c or 'sold' in c) 
            and not any(bad in c for bad in excluded_words)
        ]
        
        # Prioritize 'sold price' or 'closed price', otherwise 'list price'
        price_col = next((c for c in possible_price_cols if 'sold' in c or 'closed' in c), None)
        if not price_col and possible_price_cols:
            price_col = possible_price_cols[0]

        # C. Calculate Counts
        # Convert column to string first to avoid errors
        status_series = df[status_col].astype(str)
        
        sold_mask = status_series.str.contains('sold|closed|settled', case=False, na=False)
        active_mask = status_series.str.contains('active|avail|coming', case=False, na=False)
        failed_mask = status_series.str.contains('exp|with|canc|term', case=False, na=False)
        
        sold = df[sold_mask].shape[0]
        active = df[active_mask].shape[0]
        failed = df[failed_mask].shape[0]
        
        # D. Math
        sales_pm = sold / months
        moi = (active / sales_pm) if sales_pm > 0 else 99.9
        attempts = sold + failed
        success = (sold / attempts * 100) if attempts > 0 else 0
        
        # E. Price Calculation (Clean Currency Symbols)
        avg_price = 0
        if price_col:
            raw_prices = df[sold_mask][price_col].astype(str)
            # Remove '$' and ','
            clean_prices = raw_prices.str.replace(r'[$,]', '', regex=True)
            # Convert to number
            numeric_prices = pd.to_numeric(clean_prices, errors='coerce')
            avg_price = numeric_prices.mean()

        return {
            "months_inventory": round(moi, 2),
            "success_ratio": round(success, 1),
            "avg_sold_price": f"${avg_price:,.0f}" if avg_price > 0 else "N/A",
            "failed": failed,
            "sold": sold,
            "active": active
        }
    except Exception as e:
        return f"Calculation Error: {str(e)}"

# --- 4. USER INTERFACE ---
with st.sidebar:
    st.header("⚙️ Settings")
    
    # API Key Handling
    env_key = os.getenv("GOOGLE_API_KEY")
    api_key = env_key if env_key else st.text_input("🔑 API Key", type="password")
    
    st.divider()
    agent_name = st.text_input("Agent Name", value="Fernando Herboso")
    
    st.subheader("Market Data")
    uploaded_file = st.file_uploader("Upload MLS CSV", type=["csv"])
    months_analyzed = st.number_input("Months Analyzed", min_value=1, value=6)

st.title("🏠 Listing Powerhouse AI")
st.markdown("### Strategic Market Analyzer & Report Generator")

col1, col2 = st.columns([3, 1])
with col1:
    address = st.text_input("📍 Subject Property Address:", placeholder="123 Main St, City, State")

if st.button("🚀 Run Analysis"):
    if not api_key or not address or not uploaded_file:
        st.error("⚠️ Missing Data: Please provide API Key, Address, and upload the CSV.")
    else:
        # STEP 1: Process CSV (With Safety Check)
        df = pd.read_csv(uploaded_file)
        metrics = calculate_metrics(df, months_analyzed)
        
        # CRITICAL SAFETY STOP: If metrics returned an error string, stop here.
        if isinstance(metrics, str):
            st.error(f"❌ Data Error: {metrics}")
            st.warning("Please check your CSV columns.")
            st.stop()

        # STEP 2: Web Search
        with st.spinner('🌍 Searching Zillow, Redfin, & Realtor...'):
            web_raw_data = get_web_estimates(address)

        # STEP 3: Load Knowledge Base
        kb_text = load_knowledge_base()

        # STEP 4: Build Prompt
        prompt = f"""
        ACT AS: Top Real Estate Strategist for agent {agent_name}.
        OBJECTIVE: Create a Winning Listing Strategy for {address}.
        
        === MARKET INTELLIGENCE (MLS DATA) ===
        - Months of Inventory (MOI): {metrics['months_inventory']}
        - Success Ratio: {metrics['success_ratio']}%
        - Failed Listings (Expired/Withdrawn): {metrics['failed']}
        - Avg Sold Price: {metrics['avg_sold_price']}
        
        === ONLINE INTELLIGENCE (WEB SEARCH) ===
        {web_raw_data}
        
        === KNOWLEDGE BASE ===
        {kb_text[:20000]}
        
        === INSTRUCTIONS ===
        Write a comprehensive strategy report in English.
        1. **Reality Check:** Compare the Online Estimates (Zillow) vs the Real Market Data (Absorption Rate).
        2. **Pricing Strategy:** Based on the Success Ratio.
        3. **Marketing Plan:** Key steps to overcome the competition.
        4. **Seller Script:** How to handle the "I want a higher price" objection using the MOI data.
        """

        # STEP 5: Generate with Gemini
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        with st.spinner('🤖 Analyzing data & writing report...'):
            try:
                response = model.generate_content(prompt)
                report_text = response.text
                
                # Get a short summary for the PDF
                summary_prompt = f"Summarize the online price estimates found in this text in 1 sentence: {web_raw_data}"
                web_summary = model.generate_content(summary_prompt).text
                
                # Display Results
                st.success("✅ Analysis Complete!")
                
                # Dashboard
                m1, m2, m3 = st.columns(3)
                m1.metric("Absorption (MOI)", f"{metrics['months_inventory']} Mo")
                m2.metric("Success Rate", f"{metrics['success_ratio']}%")
                m3.metric("Avg Price", metrics['avg_sold_price'])
                
                st.markdown("---")
                st.markdown(report_text)
                
                # Create PDF
                pdf_bytes = create_pdf(report_text, agent_name, address, metrics, web_summary)
                
                st.download_button(
                    label="📥 Download Official PDF Report",
                    data=pdf_bytes,
                    file_name=f"Strategy_{address.replace(' ', '_')}.pdf",
                    mime="application/pdf"
                )
                
            except Exception as e:
                st.error(f"AI/Connection Error: {e}")

