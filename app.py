import streamlit as st
import pandas as pd
import google.generativeai as genai
import os
import pdfplumber
from fpdf import FPDF
from duckduckgo_search import DDGS # <--- LOS OJOS DE INTERNET

# --- CONFIGURATION ---
st.set_page_config(page_title="Listing Powerhouse AI (Connected)", page_icon="🌐", layout="wide")

# --- WEB SEARCH FUNCTION (THE "INTERNET" BRAIN) ---
def get_web_estimates(address):
    """
    Uses DuckDuckGo to search for Zillow/Redfin estimates live.
    Returns a text summary of what it found.
    """
    search_query = f"{address} price estimate zillow redfin realtor"
    results_text = ""
    
    try:
        with DDGS() as ddgs:
            # Search for top 5 results
            results = list(ddgs.text(search_query, max_results=5))
            for r in results:
                results_text += f"- Source: {r['title']}\n  Snippet: {r['body']}\n\n"
        
        if not results_text:
            return "No online estimates found (Search returned empty)."
        return results_text
    except Exception as e:
        return f"Could not connect to internet search: {e}"

# --- PDF GENERATION ---
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

def create_pdf(content, agent_name, address, metrics, web_data_summary):
    pdf = PDFReport()
    pdf.add_page()
    
    # Cover
    pdf.set_font('Arial', 'B', 24)
    pdf.ln(40)
    pdf.cell(0, 10, f"Strategic Listing Plan", 0, 1, 'C')
    pdf.set_font('Arial', '', 16)
    pdf.cell(0, 10, f"{address}", 0, 1, 'C')
    pdf.ln(20)
    pdf.set_font('Arial', 'I', 14)
    pdf.cell(0, 10, f"Prepared by: {agent_name}", 0, 1, 'C')
    
    # Metrics Page
    pdf.add_page()
    pdf.chapter_title("Market Reality Check")
    pdf.set_font('Arial', '', 11)
    
    # CSV Data
    pdf.cell(0, 10, f"Real Market Absorption (MOI): {metrics['months_inventory']} Months", 0, 1)
    pdf.cell(0, 10, f"Probability of Sale: {metrics['success_ratio']}%", 0, 1)
    
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 10, "Online Intelligence (Zillow/Redfin Data):", 0, 1)
    pdf.set_font('Arial', '', 10)
    # We add the AI summary of the web data here
    pdf.multi_cell(0, 6, web_data_summary)
    
    pdf.ln(10)
    
    # Strategy Content
    pdf.chapter_title("Strategic Execution")
    pdf.set_font('Arial', '', 11)
    
    # Clean and print Markdown content
    lines = content.split('\n')
    for line in lines:
        if line.startswith('###') or line.startswith('**'):
            pdf.set_font('Arial', 'B', 11)
            pdf.multi_cell(0, 8, line.replace('*', '').replace('#', ''))
            pdf.set_font('Arial', '', 11)
        else:
            pdf.multi_cell(0, 6, line.replace('*', ''))
            
    return pdf.output(dest='S').encode('latin-1')

# --- DATA FUNCTIONS ---
def load_knowledge_base():
    """Reads internal manuals."""
    knowledge_text = ""
    folder_path = "knowledge_base"
    if not os.path.exists(folder_path): return ""
    for filename in os.listdir(folder_path):
        try:
            file_path = os.path.join(folder_path, filename)
            if filename.lower().endswith('.pdf'):
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        extracted = page.extract_text()
                        if extracted: knowledge_text += extracted + "\n"
            elif filename.lower().endswith('.txt'):
                with open(file_path, 'r') as f: knowledge_text += f.read()
        except: pass
    return knowledge_text

def calculate_metrics(df, months_analyzed=6):
    try:
        df.columns = [c.lower().strip() for c in df.columns]
        status_col = next((c for c in df.columns if 'status' in c), None)
        price_col = next((c for c in df.columns if 'price' in c or 'list' in c), None)
        
        if not status_col: return "Error: 'Status' col not found."

        sold = df[df[status_col].str.contains('sold|closed', case=False, na=False)].shape[0]
        active = df[df[status_col].str.contains('active|avail', case=False, na=False)].shape[0]
        failed = df[df[status_col].str.contains('exp|with|canc', case=False, na=False)].shape[0]
        
        sales_per_month = sold / months_analyzed
        months_inventory = (active / sales_per_month) if sales_per_month > 0 else 99
        total_attempts = sold + failed
        success_ratio = (sold / total_attempts * 100) if total_attempts > 0 else 0
        avg_price = df[sold == True][price_col].mean() if price_col else 0 

        return {
            "sold": sold, "active": active, "failed": failed,
            "success_ratio": round(success_ratio, 1),
            "months_inventory": round(months_inventory, 2),
            "avg_sold_price": f"${avg_price:,.0f}" if price_col else "N/A"
        }
    except Exception as e: return str(e)

# --- INTERFACE ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=50)
    st.title("Settings")
    
    env_key = os.getenv("GOOGLE_API_KEY")
    api_key = env_key if env_key else st.text_input("🔑 API Key", type="password")
    
    st.divider()
    agent_name = st.text_input("Agent Name", value="Fernando Herboso")
    uploaded_file = st.file_uploader("Upload MLS CSV", type=["csv"])
    months_analyzed = st.number_input("Months Analyzed", value=6)

st.title("🌐 Smart Listing Agent (Connected)")

col1, col2 = st.columns([3, 1])
with col1:
    address = st.text_input("📍 Property Address (Subject):", placeholder="123 Main St, City, State")

if st.button("🚀 Analyze Market & Internet"):
    if not api_key or not address or not uploaded_file:
        st.error("⚠️ Missing Data: API Key, Address, or CSV.")
    else:
        # 1. LIVE INTERNET SEARCH
        with st.spinner('🌍 Searching Zillow, Redfin, and Realtor.com...'):
            web_raw_data = get_web_estimates(address)
       # 2. READ CSV
        df = pd.read_csv(uploaded_file)
        metrics = calculate_metrics(df, months_analyzed)

        # --- BLOQUE DE SEGURIDAD (AÑADIR ESTO) ---
        if isinstance(metrics, str):
            st.error(f"❌ Error en el CSV: {metrics}")
            st.warning("Consejo: Abre tu CSV y asegúrate de que haya una columna llamada 'Status', 'Estado' o 'Current Status'.")
            st.stop() # <--- ESTO DETIENE EL PROGRAMA ANTES DE QUE FALLE
        # -----------------------------------------

        # 3. LOAD KNOWLEDGE
        kb_text = load_knowledge_base()

        # 4. INTELLIGENT PROMPT
        prompt = f"""
        ACT AS: Top Real Estate Strategist for {agent_name}.
        OBJECTIVE: Create a Winning Listing Strategy for {address}.
        
        === LIVE WEB DATA (From Internet Search) ===
        I have searched the web for Zillow/Redfin estimates. Here is the raw text found:
        {web_raw_data}
        
        INSTRUCTION FOR WEB DATA:
        - Analyze the snippets above.
        - Extract any price estimates mentioned (e.g., "Zestimate: $500k").
        - If prices differ from the CSV Market Data, highlight the discrepancy in the report.
        - Create a specific summary sentence like: "Online algorithms range from $X to $Y."
        ============================================
        
        === HARD MARKET DATA (From MLS CSV) ===
        - MOI (Months of Inventory): {metrics['months_inventory']}
        - Success Ratio: {metrics['success_ratio']}%
        - Avg Sold Price in Neighborhood: {metrics['avg_sold_price']}
        
        === KNOWLEDGE BASE ===
        {kb_text[:20000]}
        
        === TASK ===
        Write a strategy report.
        1. **Online vs. Reality:** Compare the Zillow/Online estimates (if found) vs. the Real MLS Data. Use the script: "Zillow thinks your home is worth X, but the absorption rate suggests..."
        2. **Pricing Strategy:** Based on the Success Ratio.
        3. **Executive Summary:** Urgency based on MOI.
        4. **Seller Script:** How to handle the "Zestimate" objection using the data above.
        """

        # 5. GENERATE
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        with st.spinner('🤖 Synthesizing Web Data + MLS Data...'):
            try:
                response = model.generate_content(prompt)
                report_text = response.text
                
                # Extract a short summary of web findings for the PDF
                web_summary_prompt = f"Summarize these search results in 1 sentence focusing on price estimates: {web_raw_data}"
                web_summary = model.generate_content(web_summary_prompt).text
                
                # Display
                st.markdown("### 📝 Strategic Analysis")
                st.info(f"🌐 **Internet Intelligence:** {web_summary}")
                st.markdown(report_text)
                
                # PDF
                pdf_bytes = create_pdf(report_text, agent_name, address, metrics, web_summary)
                
                st.download_button(
                    label="📥 Download Smart PDF Report",
                    data=pdf_bytes,
                    file_name=f"Smart_Report_{address.replace(' ', '_')}.pdf",
                    mime="application/pdf"
                )
                
            except Exception as e:
                st.error(f"Error: {e}")
            except Exception as e:
                st.error(f"Error: {e}")



