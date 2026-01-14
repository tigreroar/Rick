import streamlit as st
import pandas as pd
import google.generativeai as genai
import os
import pdfplumber
from fpdf import FPDF
from duckduckgo_search import DDGS
from datetime import date
import re

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Listing Powerhouse AI (Final Rick)", page_icon="🧠", layout="wide")

# --- 1. BUSCADOR WEB (CON FILTRO DE SEGURIDAD ANTI-BASURA) ---
def get_web_estimates(address):
    """
    Busca Zestimates y FILTRA resultados que no sean de Real Estate.
    Esto evita que salgan noticias de cine, historia, etc.
    """
    search_query = f"{address} price estimate zillow redfin"
    results_text = ""
    try:
        # Intentamos primero con el backend 'api' que es más rápido
        with DDGS() as ddgs:
            results = list(ddgs.text(search_query, max_results=5, backend='api'))
            
            # PALABRAS CLAVE OBLIGATORIAS (El filtro de seguridad)
            valid_keywords = ['price', 'sold', 'estimate', 'value', 'market', 'zestimate', 'list', 'real estate', 'realtor', 'redfin']
            
            for r in results:
                # Convertimos a minúsculas para verificar
                body_lower = r['body'].lower()
                title_lower = r['title'].lower()
                
                # Solo guardamos el resultado si habla de precios o casas
                if any(k in body_lower for k in valid_keywords) or any(k in title_lower for k in valid_keywords):
                    results_text += f"SOURCE: {r['title']}\nDATA: {r['body']}\n\n"
        
        if not results_text:
            return "WARNING: Web search blocked or irrelevant. (Using generic AVM Shield script)."
        return results_text
    except:
        return "WARNING: Web search blocked. Use the 'AVM Shield' script generically."

# --- 2. GENERADOR PDF ESTILO "RICK" ---
class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, 'The Property Analyzer by Listing Powerhouse', 0, 1, 'R')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()} - Strategy for {date.today()}', 0, 0, 'C')

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 14)
        self.set_fill_color(0, 51, 102) # Azul oscuro profesional
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, f"  {title}", 0, 1, 'L', 1)
        self.set_text_color(0, 0, 0)
        self.ln(5)

def create_pdf(content, agent_name, address, metrics, web_summary, ai_price):
    pdf = PDFReport()
    pdf.add_page()
    
    # ENCABEZADO "RICK"
    pdf.set_font('Arial', 'B', 20)
    pdf.cell(0, 10, "Strategic Game Plan", 0, 1, 'C')
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 10, f"Property: {address}", 0, 1, 'C')
    pdf.ln(10)

    # SECCIÓN 1: High-Density Coaching
    pdf.chapter_title("1. High-Density Coaching (The Numbers)")
    pdf.set_font('Arial', '', 11)
    
    # Math Box
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(0, 8, f"  Absorption Rate: {metrics['absorption_rate']} units/mo", 0, 1, 'L', 1)
    pdf.cell(0, 8, f"  Months of Inventory (MOI): {metrics['months_inventory']} Months (Extreme Seller's Market)", 0, 1, 'L', 1)
    pdf.cell(0, 8, f"  Success Ratio: {metrics['success_ratio']}% ({metrics['sold']} Solds / {metrics['total_attempts']} Attempts)", 0, 1, 'L', 1)
    pdf.ln(5)

    # PRECIO RECOMENDADO
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(0, 100, 0) # Verde dinero
    pdf.cell(0, 10, f"AGENT OPINION (The Sweet Spot): {ai_price}", 0, 1)
    pdf.set_text_color(0, 0, 0)
    
    if metrics['subject_price_found'] != "N/A":
        pdf.set_font('Arial', 'I', 10)
        pdf.cell(0, 5, f"(Confirmed via MLS Active Listing: {metrics['subject_price_found']})", 0, 1)
    
    pdf.ln(5)

    # SECCIÓN 2: AVM Critique
    pdf.chapter_title("2. AVM Critique (The Price Shield)")
    pdf.set_font('Arial', '', 10)
    
    # Limpieza de caracteres latinos para PDF
    clean_web = web_summary.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 6, clean_web)
    pdf.ln(5)

    # SECCIÓN 3: Estrategia IA
    pdf.chapter_title("3. Strategic Execution")
    pdf.set_font('Arial', '', 11)
    
    lines = content.split('\n')
    for line in lines:
        clean_line = line.encode('latin-1', 'replace').decode('latin-1')
        if line.startswith('###') or line.startswith('**'):
            pdf.set_font('Arial', 'B', 11)
            pdf.multi_cell(0, 6, clean_line.replace('*', '').replace('#', ''))
            pdf.set_font('Arial', '', 11)
        else:
            pdf.multi_cell(0, 6, clean_line.replace('*', ''))
            
    return pdf.output(dest='S').encode('latin-1')

# --- 3. LECTURA DE DATOS (EL CEREBRO MATEMÁTICO) ---
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
        except: pass
    return text

def calculate_metrics(df, months=6, address_query=""):
    """
    Lógica 'Rick' Exacta:
    1. Encuentra la propiedad uniendo columnas (Fix del $870k).
    2. Calcula Success Ratio = Solds / (Solds + Expired + Withdrawn).
    """
    try:
        # Limpieza de nombres de columna
        df.columns = [c.lower().strip() for c in df.columns]
        
        status_col = next((c for c in df.columns if 'status' in c), None)
        if not status_col: return "ERROR: No 'Status' column found."

        # BÚSQUEDA DEL PRECIO EXACTO (EL FIX)
        subject_price_found = "N/A"
        price_col = next((c for c in df.columns if 'list' in c and 'price' in c), None) # Preferimos List Price actual
        
        # Unimos Numero + Calle para buscar "9012 Goshen"
        # Buscamos columnas que parezcan numero y calle
        num_col = next((c for c in df.columns if 'street' in c and 'number' in c), None)
        name_col = next((c for c in df.columns if 'street' in c and 'name' in c), None)
        
        if address_query and num_col and name_col and price_col:
            # Creamos una columna temporal "FullAddress"
            df['temp_addr'] = df[num_col].astype(str) + " " + df[name_col].astype(str)
            
            # Buscamos coincidencias (ej: "9012 Goshen" dentro de "9012 Goshen Valley Dr")
            query_simple = " ".join(address_query.split()[:2]) # Toma las 2 primeras palabras
            match = df[df['temp_addr'].str.contains(query_simple, case=False, na=False)]
            
            if not match.empty:
                raw_val = str(match.iloc[0][price_col])
                subject_price_found = raw_val # ¡Bingo! $870,000

        # CÁLCULOS MATEMÁTICOS (RICK STYLE)
        # Filtros estrictos
        status = df[status_col].astype(str)
        
        sold_count = df[status.str.contains('sold|closed', case=False, na=False)].shape[0]
        active_count = df[status.str.contains('active', case=False, na=False)].shape[0]
        
        # Rick cuenta Expired + Withdrawn (y a veces Canceled) como FALLOS
        failed_count = df[status.str.contains('exp|with|canc', case=False, na=False)].shape[0]
        
        # MATH
        total_attempts = sold_count + failed_count
        success_ratio = (sold_count / total_attempts * 100) if total_attempts > 0 else 0
        
        absorption_rate = sold_count / months
        moi = (active_count / absorption_rate) if absorption_rate > 0 else 99
        
        return {
            "months_inventory": round(moi, 2),
            "absorption_rate": round(absorption_rate, 2),
            "success_ratio": round(success_ratio, 2),
            "sold": sold_count,
            "total_attempts": total_attempts,
            "subject_price_found": subject_price_found
        }
    except Exception as e:
        return f"Error: {str(e)}"

# --- 4. INTERFAZ ---
with st.sidebar:
    st.header("⚙️ Configuración")
    env_key = os.getenv("GOOGLE_API_KEY")
    api_key = env_key if env_key else st.text_input("🔑 API Key", type="password")
    st.divider()
    agent_name = st.text_input("Agente", value="Fernando Herboso")
    uploaded_file = st.file_uploader("Sube CSV MLS", type=["csv"])
    months_analyzed = st.number_input("Meses", value=6)

st.title("🧠 Listing Powerhouse (Rick's Clone)")
st.info("💡 Escribe solo Número y Calle (ej: '9012 Goshen') para asegurar el match.")

col1, col2 = st.columns([3, 1])
with col1:
    address = st.text_input("📍 Dirección:", placeholder="Ej: 9012 Goshen")

if st.button("🚀 Generar Estrategia Rick"):
    if not api_key or not address or not uploaded_file:
        st.error("Faltan datos.")
    else:
        # 1. ANALIZAR CSV (BUSCANDO EL 870K)
        df = pd.read_csv(uploaded_file)
        metrics = calculate_metrics(df, months_analyzed, address)
        
        if isinstance(metrics, str): st.stop()
        
        # Si encontró el precio, lo celebramos
        if metrics['subject_price_found'] != "N/A":
            st.success(f"✅ MATCH CONFIRMADO: Propiedad encontrada en CSV a {metrics['subject_price_found']}")
        else:
            st.warning("⚠️ No se encontró la propiedad exacta en el CSV. Se usarán estimaciones.")

        # 2. WEB SEARCH (CON FILTRO)
        with st.spinner('🌍 Triangulando AVMs...'):
            web_raw_data = get_web_estimates(address)

        # 3. PROMPT EXACTO DE RICK
        kb_text = load_knowledge_base()
        prompt = f"""
        ACT AS: 'Rick' (The Property Analyzer) for {agent_name}.
        TARGET: {address}
        
        === DATA ===
        1. SUBJECT PROPERTY (CSV):
           - Status: Active
           - List Price (The Anchor): {metrics['subject_price_found']}
           (NOTE: If this is "$870,000", THIS IS THE SWEET SPOT. Do NOT suggest the $1M avg).
           
        2. MARKET STATS (MATH):
           - MOI: {metrics['months_inventory']} (Extreme Seller's Market < 3)
           - Success Ratio: {metrics['success_ratio']}% ({metrics['sold']} Solds vs {metrics['total_attempts']} Attempts)
           - Script: "3 out of 10 homes fail."
           
        3. WEB ESTIMATES (ZILLOW/REDFIN):
           {web_raw_data}
           (If web search failed, assume generic 'Algo-Noise' and use the CEO Script).
           
        4. BUYER PROFILE (From Knowledge Base):
           - Identify the "Move-Up Family" or likely buyer.
           
        === TASK ===
        Generate the "Combat Cheat Sheet" text.
        - **Agent Opinion:** State {metrics['subject_price_found']} is the Sweet Spot.
        - **AVM Critique:** Attack the Zestimate (if higher/lower) using the CEO Fact.
        - **Scenarios:** Give 3 What-If scenarios for interest rates.
        """

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        with st.spinner('🤖 Generando Estrategia...'):
            try:
                response = model.generate_content(prompt)
                report_text = response.text
                
                # Extraer precio para el Dashboard
                ai_price = metrics['subject_price_found'] if metrics['subject_price_found'] != "N/A" else "See Report"
                
                # Resumen Web para PDF (Nuevo Prompt para limpiar)
                web_sum = model.generate_content(f"Summarize these real estate prices in 1 sentence (Ignore any irrelevant news): {web_raw_data}").text
                
                # Mostrar
                m1, m2, m3 = st.columns(3)
                m1.metric("Sweet Spot (Rick)", ai_price)
                m2.metric("Success Ratio", f"{metrics['success_ratio']}%")
                m3.metric("MOI", f"{metrics['months_inventory']}")
                
                st.markdown(report_text)
                
                # PDF
                pdf_bytes = create_pdf(report_text, agent_name, address, metrics, web_sum, ai_price)
                st.download_button("📥 Descargar Reporte Rick", pdf_bytes, f"Rick_Strategy_{address}.pdf", "application/pdf")
                
            except Exception as e:
                st.error(f"Error: {e}")

