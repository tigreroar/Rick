import streamlit as st
import pandas as pd
import google.generativeai as genai
import os
import pdfplumber
from fpdf import FPDF
from duckduckgo_search import DDGS
from datetime import date
import re

# --- CONFIGURACIÓN ESTÁNDAR ---
st.set_page_config(page_title="Listing Powerhouse AI (Rick)", page_icon="🧠", layout="wide")

# --- 1. MOTOR DE BÚSQUEDA (INTELIGENCIA EXTERNA) ---
def get_web_estimates(address):
    """Busca en Zillow/Redfin para tener el contexto externo."""
    search_query = f"{address} price estimate zillow redfin realtor"
    results_text = ""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(search_query, max_results=5))
            for r in results:
                results_text += f"SOURCE: {r['title']}\nSUMMARY: {r['body']}\n\n"
        
        if not results_text:
            return "WARNING: Web search blocked. AI will rely only on MLS Data."
        return results_text
    except Exception as e:
        return f"Search Error: {e}"

# --- 2. MOTOR DE REPORTES (PDF) ---
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

def create_pdf(content, agent_name, address, metrics, web_summary, ai_price):
    pdf = PDFReport()
    pdf.add_page()
    # PORTADA
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
    
    # DASHBOARD
    pdf.add_page()
    pdf.chapter_title("Strategic Pricing Analysis")
    pdf.set_font('Arial', '', 11)
    
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 15, f"RECOMMENDED TARGET PRICE: {ai_price}", 0, 1)
    pdf.set_font('Arial', '', 11)
    
    if isinstance(metrics, dict):
        pdf.cell(0, 10, "Market Conditions (The 'Why'):", 0, 1)
        pdf.cell(0, 8, f"- Inventory Speed (MOI): {metrics['months_inventory']} Months", 0, 1)
        pdf.cell(0, 8, f"- Probability of Selling: {metrics['success_ratio']}%", 0, 1)
        pdf.cell(0, 8, f"- Neighborhood Avg: {metrics['avg_sold_price']}", 0, 1)
        if metrics.get('subject_price_found') != "N/A":
             pdf.set_font('Arial', 'B', 11)
             pdf.cell(0, 8, f"- Subject Property (List) Price found in CSV: {metrics['subject_price_found']}", 0, 1)
             pdf.set_font('Arial', '', 11)

    pdf.ln(5)
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 10, "Online Intelligence (AVM Context):", 0, 1)
    pdf.set_font('Arial', '', 10)
    clean_web = web_summary.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 6, clean_web)
    pdf.ln(10)
    
    # CONTENIDO
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

# --- 3. LECTURA DE DATOS (ESTO ES LO QUE NO DEBES TOCAR) ---
def load_knowledge_base():
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

def calculate_metrics(df, months=6, address_query=""):
    """
    1. Limpia el CSV.
    2. Calcula métricas (MOI, Success Ratio).
    3. Busca el precio de la casa sujeto SI existe en el CSV.
    """
    try:
        df.columns = [c.lower().strip() for c in df.columns]
        
        # A. Encontrar Columna Status
        status_col = next((c for c in df.columns if 'status' in c), None)
        if not status_col: return "ERROR: No se encontró columna 'Status'."

        # B. Encontrar Columna Precio (Ignorando Fechas)
        excluded = ['date', 'agent', 'office', 'code', 'phone', 'zip', 'id']
        price_cols = [c for c in df.columns if ('price' in c or 'list' in c or 'sold' in c) and not any(x in c for x in excluded)]
        # Preferimos precio de lista actual o precio vendido
        price_col = next((c for c in price_cols if 'list' in c), price_cols[0] if price_cols else None)
        
        # C. Lógica de Búsqueda de Propiedad Sujeto
        subject_price_found = "N/A"
        if address_query and price_col:
            # Buscamos en todas las columnas de texto la coincidencia (ej: "9012 Goshen")
            # Esto une todas las columnas en una sola linea de texto por fila para buscar
            df['search_index'] = df.astype(str).agg(' '.join, axis=1)
            match = df[df['search_index'].str.contains(address_query, case=False, na=False)]
            if not match.empty:
                raw = str(match.iloc[0][price_col])
                subject_price_found = raw # ej: $870,000

        # D. Cálculos Matemáticos
        status = df[status_col].astype(str)
        sold = df[status.str.contains('sold|closed', case=False, na=False)].shape[0]
        active = df[status.str.contains('active|avail', case=False, na=False)].shape[0]
        failed = df[status.str.contains('exp|with|canc|term', case=False, na=False)].shape[0]
        
        sales_pm = sold / months
        moi = (active / sales_pm) if sales_pm > 0 else 99.9
        attempts = sold + failed
        success = (sold / attempts * 100) if attempts > 0 else 0
        
        avg_price = 0
        if price_col:
            # Limpieza de $ y , para calcular promedio
            clean_p = df[status.str.contains('sold|closed', case=False, na=False)][price_col].astype(str).str.replace(r'[$,]', '', regex=True)
            avg_price = pd.to_numeric(clean_p, errors='coerce').mean()

        return {
            "months_inventory": round(moi, 2),
            "success_ratio": round(success, 1),
            "avg_sold_price": f"${avg_price:,.0f}" if avg_price > 0 else "N/A",
            "failed": failed,
            "subject_price_found": subject_price_found
        }
    except Exception as e:
        return f"Error de Cálculo: {str(e)}"

# --- 4. INTERFAZ (FRONTEND) ---
with st.sidebar:
    st.header("⚙️ Configuración")
    env_key = os.getenv("GOOGLE_API_KEY")
    api_key = env_key if env_key else st.text_input("🔑 API Key", type="password")
    st.divider()
    agent_name = st.text_input("Nombre Agente", value="Fernando Herboso")
    uploaded_file = st.file_uploader("Sube CSV MLS", type=["csv"])
    months_analyzed = st.number_input("Meses Analizados", value=6)

st.title("🧠 Listing Powerhouse AI (Rick Mode)")
st.info("💡 TIP: En dirección, escribe solo 'Número + Calle' (ej: 9012 Goshen) para mejor coincidencia.")

col1, col2 = st.columns([3, 1])
with col1:
    address = st.text_input("📍 Dirección Propiedad Sujeto:", placeholder="Ej: 9012 Goshen")

if st.button("🚀 Generar Estrategia"):
    if not api_key or not address or not uploaded_file:
        st.error("⚠️ Faltan datos (Key, Dirección o CSV).")
    else:
        # 1. ANALIZAR DATOS INTERNOS
        df = pd.read_csv(uploaded_file)
        metrics = calculate_metrics(df, months_analyzed, address)
        
        if isinstance(metrics, str): # Freno de seguridad
            st.error(metrics)
            st.stop()
            
        if metrics['subject_price_found'] != "N/A":
            st.success(f"✅ ¡Encontrada en CSV! Precio Listado: {metrics['subject_price_found']}")
        else:
            st.warning("⚠️ No encontrada en CSV (usaremos IA para estimar precio).")

        # 2. ANALIZAR DATOS EXTERNOS
        with st.spinner('🌍 Consultando Zillow/Redfin...'):
            web_raw_data = get_web_estimates(address)

        # 3. LEER DOCTRINA
        kb_text = load_knowledge_base()

        # 4. CEREBRO IA (TRIANGULACIÓN)
        prompt = f"""
        ACT AS: Real Estate Analyst 'Rick' for {agent_name}.
        DATE: {date.today().strftime('%B %d, %Y')}
        TARGET: {address}
        
        === DATA TRIANGULATION ===
        1. INTERNAL DATA (CSV):
           - Subject Property Price (if found): {metrics['subject_price_found']}
           - Market Speed (MOI): {metrics['months_inventory']} Mo
           - Success Rate: {metrics['success_ratio']}%
           - Neighborhood Avg: {metrics['avg_sold_price']}
           
        2. EXTERNAL DATA (WEB):
           {web_raw_data}
           
        3. DOCTRINE (KNOWLEDGE BASE):
           {kb_text[:20000]}
           
        === MISSION ===
        Determine the Strategy & Price.
        
        A. PRICING DECISION:
           - If Subject Price is found in CSV ({metrics['subject_price_found']}), THAT IS YOUR ANCHOR. Validate it.
           - If not found, use Web Data + Neighborhood Avg to propose a "Sweet Spot".
           - Use the MOI ({metrics['months_inventory']}) to justify urgency.
           
        B. REPORT GENERATION:
           - Write the "Strategic Listing Plan".
           - Include the "AVM Shield" script (Zillow vs Reality).
           - Explain the "Success Ratio" (Failure risk).
           
        FORMAT: Start with "RECOMMENDED PRICE: $XXX,XXX" on the first line.
        """

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        with st.spinner('🤖 Rick está pensando...'):
            try:
                # Generar
                response = model.generate_content(prompt)
                report_text = response.text
                
                # Extraer Precio Recomendado
                match = re.search(r"RECOMMENDED PRICE:\s*(\$[\d,]+)", report_text)
                ai_price = match.group(1) if match else metrics['subject_price_found']
                
                # Resumen Web
                web_sum = model.generate_content(f"Summarize web prices in 1 sentence: {web_raw_data}").text
                
                # Mostrar
                m1, m2, m3 = st.columns(3)
                m1.metric("Precio Objetivo", ai_price)
                m2.metric("Probabilidad Éxito", f"{metrics['success_ratio']}%")
                m3.metric("Inventario", f"{metrics['months_inventory']} Meses")
                
                st.markdown(report_text)
                
                # PDF
                pdf_bytes = create_pdf(report_text, agent_name, address, metrics, web_sum, ai_price)
                st.download_button("📥 Descargar Reporte PDF", pdf_bytes, f"Rick_Strategy_{address}.pdf", "application/pdf")
                
            except Exception as e:
                st.error(f"Error IA: {e}")
