import streamlit as st
import pandas as pd
import google.generativeai as genai
import os
import pdfplumber
from fpdf import FPDF
from duckduckgo_search import DDGS
from datetime import date
import re

# --- CONFIGURATION ---
st.set_page_config(page_title="Listing Powerhouse AI (Rick Logic)", page_icon="🧠", layout="wide")

# --- 1. INTERNET SEARCH (THE "AVM" CHECK) ---
def get_web_estimates(address):
    """Searches for Zestimates/Redfin values to triangulate price."""
    search_query = f"{address} price estimate zillow redfin realtor"
    results_text = ""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(search_query, max_results=5))
            for r in results:
                results_text += f"SOURCE: {r['title']}\nTEXT: {r['body']}\n\n"
        
        if not results_text:
            return "WARNING: Web search blocked. AI will rely on Market Averages."
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

def create_pdf(content, agent_name, address, metrics, web_summary, ai_price_recommendation):
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
    
    # METRICS DASHBOARD
    pdf.add_page()
    pdf.chapter_title("Strategic Pricing Analysis")
    pdf.set_font('Arial', '', 11)
    
    # THE RICK LOGIC DISPLAY
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, f"AGENT'S RECOMMENDED PRICE: {ai_price_recommendation}", 0, 1)
    pdf.set_font('Arial', '', 11)
    
    if isinstance(metrics, dict):
        pdf.ln(5)
        pdf.cell(0, 10, "Market Conditions (The 'Why'):", 0, 1)
        pdf.cell(0, 10, f"- Absorption Rate (MOI): {metrics['months_inventory']} Months", 0, 1)
        pdf.cell(0, 10, f"- Success Probability: {metrics['success_ratio']}%", 0, 1)
        pdf.cell(0, 10, f"- Neighborhood Avg Price: {metrics['avg_sold_price']}", 0, 1)
    
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 10, "Online Intelligence (AVM Context):", 0, 1)
    pdf.set_font('Arial', '', 10)
    
    clean_web = web_summary.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 6, clean_web)
    pdf.ln(10)
    
    # REPORT CONTENT
    pdf.chapter_title("Strategic Execution Plan")
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

# --- 3. KNOWLEDGE & DATA ---
def load_knowledge_base():
    """Reads 'The Buyer Profiler' and 'AVM Guide' from folder."""
    text = ""
    path = "conocimiento"
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
    Calculates pure market stats. Does NOT try to find the subject property price anymore.
    We leave the pricing strategy to the AI.
    """
    try:
        df.columns = [c.lower().strip() for c in df.columns]
        
        status_col = next((c for c in df.columns if 'status' in c), None)
        if not status_col: return "ERROR: 'Status' column missing."

        excluded_words = ['date', 'agent', 'office', 'code', 'phone', 'zip', 'id']
        possible_price_cols = [c for c in df.columns if ('price' in c or 'list' in c or 'sold' in c) and not any(x in c for x in excluded_words)]
        price_col = next((c for c in possible_price_cols if 'sold' in c or 'closed' in c), possible_price_cols[0] if possible_price_cols else None)
        
        status_series = df[status_col].astype(str)
        sold = df[status_series.str.contains('sold|closed', case=False, na=False)].shape[0]
        active = df[status_series.str.contains('active|avail', case=False, na=False)].shape[0]
        failed = df[status_series.str.contains('exp|with|canc|term', case=False, na=False)].shape[0]
        
        sales_pm = sold / months
        moi = (active / sales_pm) if sales_pm > 0 else 99.9
        attempts = sold + failed
        success = (sold / attempts * 100) if attempts > 0 else 0
        
        avg_price = 0
        if price_col:
            clean_prices = df[status_series.str.contains('sold|closed', case=False, na=False)][price_col].astype(str).str.replace(r'[$,]', '', regex=True)
            avg_price = pd.to_numeric(clean_prices, errors='coerce').mean()

        return {
            "months_inventory": round(moi, 2),
            "success_ratio": round(success, 1),
            "avg_sold_price": f"${avg_price:,.0f}" if avg_price > 0 else "N/A",
            "failed": failed
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

st.title("🧠 Rick's Strategic Brain (Full AI)")
st.markdown("### Market Analysis + AVM Triangulation")

col1, col2 = st.columns([3, 1])
with col1:
    address = st.text_input("📍 Subject Property Address:", placeholder="e.g. 9012 Goshen Valley")

if st.button("🚀 Analyze & Propose Price"):
    if not api_key or not address or not uploaded_file:
        st.error("Missing Data.")
    else:
        # 1. Market Stats (The "Ground Truth")
        df = pd.read_csv(uploaded_file)
        metrics = calculate_metrics(df, months_analyzed)
        
        if isinstance(metrics, str):
            st.error(metrics)
            st.stop()

        # 2. Web Search (The "Public Opinion")
        with st.spinner('🌍 Searching Zillow/Redfin for AVM data...'):
            web_raw_data = get_web_estimates(address)

        # 3. Knowledge Base (The "Doctrine")
        kb_text = load_knowledge_base()

        # 4. PROMPT: THE BRAIN OF RICK
        prompt = f"""
        ACT AS: Real Estate Strategist 'Rick' for agent {agent_name}.
        DATE: {date.today().strftime('%B %d, %Y')}
        TARGET PROPERTY: {address}
        
        === SOURCE 1: MARKET HARD DATA (CSV) ===
        - Market Speed (MOI): {metrics['months_inventory']} Months
        - Success Probability: {metrics['success_ratio']}%
        - Neighborhood Avg Price: {metrics['avg_sold_price']}
        
        === SOURCE 2: ONLINE AVM DATA (WEB) ===
        {web_raw_data}
        
        === SOURCE 3: INTERNAL DOCTRINE (PDFs) ===
        (Refer to 'The Buyer Profiler' and 'AVM Interpretation Guide' logic in your memory)
        {kb_text[:20000]}
        
        === MISSION ===
        You are not just reporting data. You are an EXPERT ANALYST.
        1. **TRIANGULATE THE PRICE:**
           - Look at the Zillow/Redfin estimates in Source 2.
           - Look at the Neighborhood Avg in Source 1.
           - Apply the "AVM Interpretation Guide" logic: If the MOI is {metrics['months_inventory']}, are Zestimates likely high or low?
           - **DETERMINE A "SWEET SPOT" PRICE.** (e.g., if Zillow says 950k but Avg is 900k and market is slowing, propose 925k).
        
        2. **WRITE THE STRATEGY:**
           - **The AVM Shield:** Acknowledge what Zillow says, but use the "AVM Interpretation Guide" to explain why your proposed price is better.
           - **Buyer Profile:** Based on "The Buyer Profiler", who is the target buyer for this price point?
           - **Success Math:** Explain the {metrics['success_ratio']}% success rate.
        
        === OUTPUT FORMAT ===
        Start your response with a dedicated line: "RECOMMENDED PRICE: $XXX,XXX"
        Then write the full strategy report.
        """

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        with st.spinner('Triangulating data sources...'):
            try:
                # A. Generate Strategy
                response = model.generate_content(prompt)
                report_text = response.text
                
                # B. Extract the AI's Recommended Price using Regex
                # We look for the pattern "RECOMMENDED PRICE: $..."
                match = re.search(r"RECOMMENDED PRICE:\s*(\$[\d,]+)", report_text)
                ai_price = match.group(1) if match else "See Report"
                
                # C. Summary of Web Data for PDF
                web_summary = model.generate_content(f"Summarize the online price estimates found here in 1 sentence: {web_raw_data}").text
                
                # Display Results
                st.success(f"✅ Analysis Complete. Rick recommends: {ai_price}")
                
                m1, m2, m3 = st.columns(3)
                m1.metric("Rick's Price", ai_price, "AI Generated")
                m2.metric("Success Ratio", f"{metrics['success_ratio']}%")
                m3.metric("Inventory", f"{metrics['months_inventory']} Mo")
                
                st.markdown(report_text)
                
                # PDF Generation
                pdf_bytes = create_pdf(report_text, agent_name, address, metrics, web_summary, ai_price)
                st.download_button("📥 Download Rick's Report", pdf_bytes, f"Rick_Strategy_{address}.pdf", "application/pdf")
                
            except Exception as e:
                st.error(f"Error: {e}")
