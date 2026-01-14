import streamlit as st
import pandas as pd
import google.generativeai as genai
import os
import pdfplumber
from fpdf import FPDF
from duckduckgo_search import DDGS
from datetime import date
import re
import requests

# --- CONFIGURACIÓN DE ALTO NIVEL ---
st.set_page_config(page_title="Rick: The Property Analyzer", layout="wide")

# --- 1. VISUAL INTELLIGENCE (AUTOMÁTICA) ---
def get_street_view_image(address, api_key):
    if not api_key: return None
    base_url = "https://maps.googleapis.com/maps/api/streetview"
    params = {'size': '600x400', 'location': address, 'key': api_key}
    try:
        response = requests.get(base_url, params=params)
        if response.status_code == 200:
            with open("temp_house.jpg", "wb") as f:
                f.write(response.content)
            return "temp_house.jpg"
    except: return None
    return None

# --- 2. ONLINE INTELLIGENCE (FILTRADO ESTRICTO) ---
def get_web_estimates(address):
    search_query = f"{address} price estimate zillow redfin"
    results_text = ""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(search_query, max_results=4, backend='api'))
            valid_keywords = ['price', 'sold', 'estimate', 'value', 'zestimate', '$', 'listing']
            for r in results:
                body_lower = r['body'].lower()
                # Filtro Anti-Alucinación: Solo data inmobiliaria real
                if any(k in body_lower for k in valid_keywords) and "oscar" not in body_lower:
                    results_text += f"SOURCE: {r['title']}\nDATA: {r['body']}\n\n"
        return results_text if results_text else None
    except: return None

# --- 3. GENERADOR DE PDF EJECUTIVO ---
class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, 'CONFIDENTIAL STRATEGIC ANALYSIS | Powered by Agent Coach AI', 0, 1, 'R')
        self.ln(5)
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Powered by Agent Coach AI | Generated: {date.today()}', 0, 0, 'C')
    def chapter_title(self, title):
        self.set_font('Arial', 'B', 14)
        self.set_fill_color(33, 47, 61)
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, f"  {title}", 0, 1, 'L', 1)
        self.set_text_color(0, 0, 0)
        self.ln(5)

def create_pdf(content, agent_name, address, metrics, web_summary, ai_price, image_path):
    pdf = PDFReport()
    pdf.add_page()
    
    # PORTADA
    pdf.set_font('Arial', 'B', 26)
    pdf.ln(10)
    pdf.cell(0, 15, "STRATEGIC GAME PLAN", 0, 1, 'C')
    pdf.set_font('Arial', '', 14)
    pdf.cell(0, 10, f"PROPERTY: {address}", 0, 1, 'C')
    
    if image_path:
        try:
            pdf.image(image_path, x=25, y=55, w=160)
            pdf.ln(115)
        except: pdf.ln(30)
    else: pdf.ln(30)

    pdf.set_font('Arial', 'I', 12)
    pdf.cell(0, 10, f"Prepared by: {agent_name}", 0, 1, 'C')
    
    # DATOS Y ESTRATEGIA
    pdf.add_page()
    pdf.chapter_title("1. Market Diagnostics")
    pdf.set_font('Arial', '', 11)
    
    pdf.set_fill_color(245, 245, 245)
    pdf.cell(0, 10, f"  Months of Inventory (MOI): {metrics['months_inventory']} Months", 0, 1, 'L', 1)
    pdf.cell(0, 10, f"  Success Probability (SR): {metrics['success_ratio']}%", 0, 1, 'L', 1)
    
    fail_rate = 100 - metrics['success_ratio']
    pdf.set_font('Arial', 'B', 11)
    pdf.set_text_color(180, 0, 0)
    pdf.cell(0, 10, f"  FAILURE RISK: {fail_rate:.1f}% (~{int(fail_rate/10)} OUT OF 10 HOMES FAIL)", 0, 1, 'L', 1)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(10)

    pdf.chapter_title("2. Recommended Pricing Position")
    pdf.set_font('Arial', 'B', 18)
    pdf.set_text_color(0, 80, 0)
    pdf.cell(0, 15, f"TARGET PRICE: {ai_price}", 0, 1)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)

    pdf.chapter_title("3. Strategic Execution Plan")
    pdf.set_font('Arial', '', 11)
    lines = content.split('\n')
    for line in lines:
        clean_line = line.encode('latin-1', 'replace').decode('latin-1')
        if any(x in clean_line for x in ["Scenario", "Strategic", "Script", "CEO"]):
            pdf.set_font('Arial', 'B', 11)
            pdf.multi_cell(0, 7, clean_line.replace('*', '').replace('#', ''))
            pdf.set_font('Arial', '', 11)
        else:
            pdf.multi_cell(0, 6, clean_line.replace('*', ''))
            
    return pdf.output(dest='S').encode('latin-1')

# --- 4. CÁLCULOS MATEMÁTICOS ---
def calculate_metrics(df, months=6, address_query=""):
    try:
        df.columns = [c.lower().strip() for c in df.columns]
        status_col = next((c for c in df.columns if 'status' in c), None)
        
        subject_price_found = "N/A"
        price_col = next((c for c in df.columns if 'list' in c and 'price' in c), None)
        num_col = next((c for c in df.columns if 'street' in c and 'number' in c), None)
        name_col = next((c for c in df.columns if 'street' in c and 'name' in c), None)
        
        if address_query and num_col and name_col and price_col:
            df['temp_addr'] = df[num_col].astype(str) + " " + df[name_col].astype(str)
            query_simple = " ".join(address_query.split()[:2])
            match = df[df['temp_addr'].str.contains(query_simple, case=False, na=False)]
            if not match.empty:
                subject_price_found = str(match.iloc[0][price_col])

        status = df[status_col].astype(str)
        sold = df[status.str.contains('sold|closed', case=False, na=False)].shape[0]
        active = df[status.str.contains('active', case=False, na=False)].shape[0]
        failed = df[status.str.contains('exp|with|canc', case=False, na=False)].shape[0]
        
        total_attempts = sold + failed
        success_ratio = (sold / total_attempts * 100) if total_attempts > 0 else 0
        ar = sold / months
        moi = (active / ar) if ar > 0 else 99
        avg_price = df[status.str.contains('sold|closed', case=False, na=False)][price_col].astype(str).str.replace(r'[$,]', '', regex=True).pipe(pd.to_numeric, errors='coerce').mean() if price_col else 0

        return {
            "months_inventory": round(moi, 2),
            "absorption_rate": round(ar, 2),
            "success_ratio": round(success_ratio, 1),
            "subject_price_found": subject_price_found,
            "avg_sold_price": f"${avg_price:,.0f}" if avg_price > 0 else "N/A"
        }
    except Exception as e: return f"Error: {str(e)}"

# --- 5. INTERFAZ Y LÓGICA DE VARIABLES ---

api_key = os.getenv("GOOGLE_API_KEY", "")
maps_key = os.getenv("MAPS_API_KEY", "")

with st.sidebar:
    st.header("⚙️ Control Panel")
    if not api_key:
        api_key = st.text_input("Gemini API Key", type="password")
    else:
        st.success("🤖 AI Engine: Connected")
        
    if not maps_key:
        maps_key = st.text_input("Google Maps Static Key", type="password")
    else:
        st.success("📸 Maps API: Linked Automatically")

    st.divider()
    agent_name = st.text_input("Agent Name", value="Fernando Herboso")
    uploaded_file = st.file_uploader("Upload MLS CSV", type=["csv"])
    months_analyzed = st.number_input("Months Analyzed", value=6)

st.title("Rick: The Property Analyzer")
st.markdown("Powered by Agent Coach AI")

address = st.text_input("📍 Property Address:", placeholder="e.g. 4339 Birchlake Ct, Alexandria, VA 22309")

if st.button("🚀 Execute Strategic Plan"):
    if not api_key or not address or not uploaded_file:
        st.error("Missing Data: Please ensure API Key, Address, and CSV are provided.")
    else:
        final_img = get_street_view_image(address, maps_key)
        df = pd.read_csv(uploaded_file)
        metrics = calculate_metrics(df, months_analyzed, address)
        with st.spinner('🌍 Analyzing Online AVMs...'):
            web_data = get_web_estimates(address)

        prompt = f"""
        YOU ARE: The Listing Powerhouse AI. 
        ROLE: Senior Strategic Analyst for {agent_name}.
        MISSION: Win the listing using authoritative, analytical data. 
        TONE: Executive, Authoritative, Proactive. NO JOKES.
        
        TARGET: {address}
        
        === DATA INTELLIGENCE ===
        - ANCHOR PRICE: {metrics['subject_price_found']}
        - MOI: {metrics['months_inventory']} (<3 = Extreme Seller's Market)
        - Success Ratio: {metrics['success_ratio']}%
        - FAILURE RATE: {100 - metrics['success_ratio']:.1f}% (Script: "Approx {int((100 - metrics['success_ratio'])/10)} out of 10 fail")
        
        === INSTRUCTIONS ===
        1. STRATEGIC PRICE: Propose {metrics['subject_price_found']} or a Sweet Spot near {metrics['avg_sold_price']}.
        2. AVM SHIELD: Compare with {web_data}. Use the "CEO Fact" to discredit Zillow.
        3. PREDICTIVE SCENARIOS: 
           - Scenario A (Stable): Market DOM prediction.
           - Scenario B (Rates Drop): Buyer pressure/bidding war prediction.
           - Scenario C (Rates Spike): Stagnation risk/Seller subsidy strategy.
        (NO math tasks for the user. YOU provide the expert prediction).
        """

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        try:
            response = model.generate_content(prompt)
            report_text = response.text
            ai_price = metrics['subject_price_found'] if metrics['subject_price_found'] != "N/A" else metrics['avg_sold_price']
            
            st.markdown(report_text)
            
            pdf_bytes = create_pdf(report_text, agent_name, address, metrics, str(web_data)[:300], ai_price, final_img)
            st.download_button("📥 Download Strategic Plan (PDF)", pdf_bytes, f"Strategy_{address}.pdf", "application/pdf")
        except Exception as e:
            st.error(f"Error: {e}")
