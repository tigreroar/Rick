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

# --- CONFIGURACIÓN DE COMANDO ---
st.set_page_config(page_title="Listing Powerhouse AI", page_icon="🦅", layout="wide")

# --- 1. VISUAL INTELLIGENCE (Google Maps / Upload) ---
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

# --- 2. ONLINE INTELLIGENCE (Blindado) ---
def get_web_estimates(address):
    """Recupera datos de Zillow/Redfin ignorando basura."""
    search_query = f"{address} price estimate zillow redfin"
    results_text = ""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(search_query, max_results=4, backend='api'))
            valid_keywords = ['price', 'sold', 'estimate', 'value', 'zestimate', '$', 'market']
            for r in results:
                body_lower = r['body'].lower()
                # Filtro estricto: Anti-Cine, Anti-Historia
                if any(k in body_lower for k in valid_keywords) and "oscar" not in body_lower and "movie" not in body_lower:
                    results_text += f"SOURCE: {r['title']}\nDATA: {r['body']}\n\n"
        return results_text if results_text else None
    except: return None

# --- 3. LIVE DOCUMENT CREATION (PDF ENGINE) ---
class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, 'STRATEGIC GAME PLAN | LISTING POWERHOUSE', 0, 1, 'R')
        self.ln(5)
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Confidential Report - Generated {date.today()}', 0, 0, 'C')
    def chapter_title(self, title):
        self.set_font('Arial', 'B', 14)
        self.set_fill_color(30, 30, 30) # Negro/Gris Ejecutivo
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, f"  {title}", 0, 1, 'L', 1)
        self.set_text_color(0, 0, 0)
        self.ln(5)

def create_pdf(content, agent_name, address, metrics, web_summary, ai_price, image_path):
    pdf = PDFReport()
    pdf.add_page()
    
    # --- SLIDE 1: VISUAL INTELLIGENCE & TITLE ---
    pdf.set_font('Arial', 'B', 24)
    pdf.cell(0, 15, "STRATEGIC LISTING PLAN", 0, 1, 'C')
    pdf.set_font('Arial', '', 14)
    pdf.cell(0, 10, f"{address}", 0, 1, 'C')
    
    if image_path:
        try:
            # Centrar imagen
            pdf.image(image_path, x=25, y=50, w=160)
            pdf.ln(110)
        except: pdf.ln(20)
    else: pdf.ln(20)

    pdf.set_font('Arial', 'I', 12)
    pdf.cell(0, 10, f"Prepared by: {agent_name}", 0, 1, 'C')
    
    # --- SLIDE 2: HIGH-DENSITY COACHING (THE MATH) ---
    pdf.add_page()
    pdf.chapter_title("1. Market Diagnostics (The Hard Truth)")
    pdf.set_font('Arial', '', 11)
    
    # Math Box
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(0, 10, f"  Absorption Rate: {metrics['absorption_rate']} units/mo", 0, 1, 'L', 1)
    pdf.cell(0, 10, f"  Months of Inventory (MOI): {metrics['months_inventory']} (Speed of Market)", 0, 1, 'L', 1)
    
    # Success Ratio Highlight
    fail_rate = 100 - metrics['success_ratio']
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 10, f"  Success Ratio: {metrics['success_ratio']}% (Sold vs. Failed)", 0, 1, 'L', 1)
    pdf.set_text_color(200, 0, 0)
    pdf.cell(0, 10, f"  FAILURE RATE: {fail_rate:.1f}% (~{int(fail_rate/10)} out of 10 homes FAIL)", 0, 1, 'L', 1)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)

    # Price Anchor
    pdf.chapter_title("2. Strategic Pricing Position")
    pdf.set_font('Arial', 'B', 16)
    pdf.set_text_color(0, 100, 0)
    pdf.cell(0, 15, f"RECOMMENDED LIST PRICE: {ai_price}", 0, 1)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Arial', '', 11)
    if metrics['subject_price_found'] != "N/A":
        pdf.cell(0, 8, "(Validated via Active MLS Data - The 'Sweet Spot')", 0, 1)
    pdf.ln(5)

    # --- SLIDE 3: STRATEGIC EXECUTION ---
    pdf.chapter_title("3. Combat Cheat Sheet")
    pdf.set_font('Arial', '', 11)
    
    # Limpieza de texto y formato
    lines = content.split('\n')
    for line in lines:
        clean_line = line.encode('latin-1', 'replace').decode('latin-1')
        if "Scenario" in line or line.startswith('###') or line.startswith('**'):
            pdf.set_font('Arial', 'B', 11)
            pdf.multi_cell(0, 7, clean_line.replace('*', '').replace('#', ''))
            pdf.set_font('Arial', '', 11)
        else:
            pdf.multi_cell(0, 6, clean_line.replace('*', ''))
            
    return pdf.output(dest='S').encode('latin-1')

# --- 4. DATA ENGINE (MATEMÁTICAS EXACTAS) ---
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
                        if p.extract_text(): text += p.extract_text() + "\n"
        except: pass
    return text

def calculate_metrics(df, months=6, address_query=""):
    try:
        df.columns = [c.lower().strip() for c in df.columns]
        status_col = next((c for c in df.columns if 'status' in c), None)
        if not status_col: return "ERROR: No 'Status' column found."

        # A. PRECIO EXACTO (9012 Goshen Fix)
        subject_price_found = "N/A"
        price_col = next((c for c in df.columns if 'list' in c and 'price' in c), None)
        num_col = next((c for c in df.columns if 'street' in c and 'number' in c), None)
        name_col = next((c for c in df.columns if 'street' in c and 'name' in c), None)
        
        if address_query and num_col and name_col and price_col:
            df['temp_addr'] = df[num_col].astype(str) + " " + df[name_col].astype(str)
            query_simple = " ".join(address_query.split()[:2])
            match = df[df['temp_addr'].str.contains(query_simple, case=False, na=False)]
            if not match.empty:
                raw_val = str(match.iloc[0][price_col])
                subject_price_found = raw_val

        # B. SUCCESS RATIO FORMULA
        # Sold / (Sold + Expired + Withdrawn) * 100
        status = df[status_col].astype(str)
        sold_count = df[status.str.contains('sold|closed', case=False, na=False)].shape[0]
        active_count = df[status.str.contains('active', case=False, na=False)].shape[0]
        
        # Fallos (Expired + Withdrawn + Canceled)
        failed_count = df[status.str.contains('exp|with|canc', case=False, na=False)].shape[0]
        
        total_attempts = sold_count + failed_count
        success_ratio = (sold_count / total_attempts * 100) if total_attempts > 0 else 0
        
        absorption_rate = sold_count / months
        moi = (active_count / absorption_rate) if absorption_rate > 0 else 99
        
        avg_price = 0
        if price_col:
            clean_p = df[status.str.contains('sold|closed', case=False, na=False)][price_col].astype(str).str.replace(r'[$,]', '', regex=True)
            avg_price = pd.to_numeric(clean_p, errors='coerce').mean()

        return {
            "months_inventory": round(moi, 2),
            "absorption_rate": round(absorption_rate, 2),
            "success_ratio": round(success_ratio, 1), # 1 decimal
            "sold": sold_count,
            "failed": failed_count,
            "total_attempts": total_attempts,
            "subject_price_found": subject_price_found,
            "avg_sold_price": f"${avg_price:,.0f}" if avg_price > 0 else "N/A"
        }
    except Exception as e: return f"Error: {str(e)}"

# --- 5. INTERFAZ ---
with st.sidebar:
    st.header("⚙️ Control Panel")
    env_key = os.getenv("GOOGLE_API_KEY")
    api_key = env_key if env_key else st.text_input("Gemini API Key", type="password")
    
    st.divider()
    st.info("📸 Visual Intelligence")
    maps_key = st.text_input("Google Maps Key (Optional)", type="password")
    
    st.divider()
    agent_name = st.text_input("Agent Name", value="Fernando Herboso")
    uploaded_file = st.file_uploader("Upload MLS CSV", type=["csv"])
    months_analyzed = st.number_input("Months Analyzed", value=6)

st.title("🦅 Listing Powerhouse AI")
st.markdown("**Status:** Operational | **Protocol:** Live-Draft")

col1, col2 = st.columns([3, 1])
with col1:
    address = st.text_input("📍 Subject Property:", placeholder="Enter: 9012 Goshen")
with col2:
    manual_photo = st.file_uploader("Upload Facade (Opt)", type=['jpg', 'jpeg'])

if st.button("🚀 Execute Strategic Plan"):
    if not api_key or not address or not uploaded_file:
        st.error("Protocol Halted: Missing Key, Address, or CSV.")
    else:
        # 1. VISUAL INTELLIGENCE
        final_img = None
        if manual_photo:
            with open("temp_house.jpg", "wb") as f: f.write(manual_photo.getbuffer())
            final_img = "temp_house.jpg"
        elif maps_key:
            final_img = get_street_view_image(address, maps_key)
            
        # 2. MARKET ANALYTICS
        df = pd.read_csv(uploaded_file)
        metrics = calculate_metrics(df, months_analyzed, address)
        if isinstance(metrics, str): st.stop()

        if metrics['subject_price_found'] != "N/A":
            st.success(f"✅ ANCHOR PRICE FOUND: {metrics['subject_price_found']}")
        else:
            st.warning("⚠️ Anchor Price not in CSV. Falling back to Market Estimation.")

        # 3. WEB SCAN
        with st.spinner('🌍 Scanning AVM Data...'):
            web_raw_data = get_web_estimates(address)
            if web_raw_data:
                web_pdf_text = "Analysis of Online Estimates:\n" + web_raw_data[:400] + "..."
            else:
                web_pdf_text = "Online AVM data unavailable. Strategy: Deploy 'AVM Shield' Script."

        # 4. STRATEGIC GENERATION (PROMPT FINAL)
        kb_text = load_knowledge_base()
        
        prompt = f"""
        YOU ARE: Listing Powerhouse AI.
        MISSION: Provide a Strategic Game Plan to win the listing for {agent_name}.
        TONE: Analytical, Authoritative, Proactive. No slang.
        
        TARGET PROPERTY: {address}
        
        === DATA INTELLIGENCE ===
        1. ANCHOR PRICE: {metrics['subject_price_found']} (If N/A, use Avg: {metrics['avg_sold_price']})
        2. MARKET VELOCITY:
           - MOI: {metrics['months_inventory']} (<3 = Extreme Seller's Market)
           - Success Ratio: {metrics['success_ratio']}% (Sold vs. Failed)
           - Failure Rate: {100 - metrics['success_ratio']:.1f}%
        3. EXTERNAL DATA: {web_pdf_text}
        
        === MANDATORY OUTPUT SECTIONS ===
        
        SECTION 1: COMBAT CHEAT SHEET - AGENT OPINION
        - State the "Sweet Spot" Price clearly.
        - Justify it: "Based on the {metrics['success_ratio']}% success rate, pricing correctly is the only way to avoid becoming a statistic."
        
        SECTION 2: AVM SHIELD (THE SCRIPT)
        - If Web Data exists, critique it.
        - If NOT, use this EXACT script: "Algorithms like Zillow are blind to condition. Even Zillow's CEO sold his home for 40% less than the Zestimate. We trust hard data."
        
        SECTION 3: PREDICTIVE SENSITIVITY (WHAT-IFS)
        - Scenario A (Stable Market): "Sale expected within 21-30 days."
        - Scenario B (Rates Drop): "Buyer frenzy likely. Multiple offers expected."
        - Scenario C (Rates Spike): "Market cools. Days on Market will exceed 45. Seller concessions may be needed."
        (DO NOT ASK THE AGENT TO CALCULATE MORTGAGE PAYMENTS).
        
        SECTION 4: BUYER PROFILE
        - Who is the specific buyer for this price point? (e.g., Move-up family).
        """

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        with st.spinner('🦅 Generating Strategic Deck...'):
            try:
                response = model.generate_content(prompt)
                report_text = response.text
                
                ai_price = metrics['subject_price_found'] if metrics['subject_price_found'] != "N/A" else metrics['avg_sold_price']
                
                # Visualización en Chat
                st.markdown(report_text)
                
                # Generar PDF
                pdf_bytes = create_pdf(report_text, agent_name, address, metrics, web_pdf_text, ai_price, final_img)
                st.download_button("📥 Download Strategic Deck (PDF)", pdf_bytes, f"Strategy_{address}.pdf", "application/pdf")
                
            except Exception as e:
                st.error(f"Execution Error: {e}")
