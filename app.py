import streamlit as st
import pandas as pd
import google.generativeai as genai
import os
from pypdf import PdfReader # Necesario para leer PDFs

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Listing Powerhouse AI", page_icon="🏠", layout="wide")

# --- FUNCIÓN 1: CARGAR CONOCIMIENTO (ARCHIVOS FIJOS) ---
def load_knowledge_base():
    """Lee todos los archivos de la carpeta 'conocimiento' y devuelve su texto."""
    knowledge_text = ""
    folder_path = "conocimiento"
    
    # Verificar si la carpeta existe
    if not os.path.exists(folder_path):
        return "ADVERTENCIA: No se encontró la carpeta 'conocimiento'."

    # Recorrer archivos
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        
        try:
            # Si es PDF
            if filename.endswith('.pdf'):
                reader = PdfReader(file_path)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                knowledge_text += f"\n--- CONTENIDO DEL ARCHIVO: {filename} ---\n{text}\n"
            
            # Si es Texto (.txt, .md, .csv)
            elif filename.endswith(('.txt', '.md', '.csv')):
                with open(file_path, 'r', encoding='utf-8') as f:
                    knowledge_text += f"\n--- CONTENIDO DEL ARCHIVO: {filename} ---\n{f.read()}\n"
                    
        except Exception as e:
            st.warning(f"No se pudo leer {filename}: {e}")
            
    return knowledge_text

# --- FUNCIÓN 2: CÁLCULOS MATEMÁTICOS (TU CSV) ---
def calculate_metrics(df):
    try:
        df.columns = [c.lower().strip() for c in df.columns]
        status_col = next((col for col in df.columns if 'status' in col), None)
        
        if not status_col: return "Error: Columna 'Status' no encontrada."

        sold = df[df[status_col].str.contains('sold|closed', case=False, na=False)].shape[0]
        expired = df[df[status_col].str.contains('expired', case=False, na=False)].shape[0]
        withdrawn = df[df[status_col].str.contains('withdrawn|cancelled', case=False, na=False)].shape[0]
        active = df[df[status_col].str.contains('active|available', case=False, na=False)].shape[0]
        
        total_failures = expired + withdrawn
        total_attempts = sold + total_failures
        
        success_ratio = (sold / total_attempts * 100) if total_attempts > 0 else 0
        sales_per_month = sold / 12
        months_inventory = (active / sales_per_month) if sales_per_month > 0 else 0
            
        return {
            "sold": sold, "expired": expired, "withdrawn": withdrawn, "active": active,
            "success_ratio": round(success_ratio, 1),
            "months_inventory": round(months_inventory, 1)
        }
    except Exception as e:
        return f"Error cálculo: {e}"

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("⚙️ Configuración")
    env_api_key = os.getenv("GOOGLE_API_KEY")
    api_key = env_api_key if env_api_key else st.text_input("API Key", type="password")
    
    st.divider()
    st.subheader("📂 Market Data (Variable)")
    uploaded_file = st.file_uploader("Sube CSV del MLS hoy", type=["csv"])
    
    st.divider()
    st.info("ℹ️ Los manuales y guías se cargan automáticamente desde la carpeta /conocimiento.")

# --- INTERFAZ PRINCIPAL ---
st.title("🏠 Listing Powerhouse AI")
address = st.text_input("📍 Dirección de la Propiedad:")

if st.button("🚀 Generar Estrategia"):
    if not api_key or not address:
        st.warning("Faltan datos.")
    else:
        # 1. Cargar Conocimiento Estático (Tus archivos PDF/TXT)
        base_knowledge = load_knowledge_base()
        
        # 2. Cargar Datos del Mercado (CSV subido hoy)
        metrics_text = "No CSV uploaded."
        metrics_display = None
        if uploaded_file:
            df = pd.read_csv(uploaded_file)
            metrics = calculate_metrics(df)
            if isinstance(metrics, dict):
                metrics_text = f"""MARKET METRICS:
                - Sold: {metrics['sold']}
                - Active: {metrics['active']}
                - Failed (Exp/With): {metrics['expired'] + metrics['withdrawn']}
                - SUCCESS RATIO: {metrics['success_ratio']}%
                - MONTHS INVENTORY: {metrics['months_inventory']}"""
                metrics_display = metrics

        # 3. Construir el Prompt Maestro
        SYSTEM_PROMPT = f"""
        You are the Listing Powerhouse AI for Fernando Herboso.
        
        === INTERNAL KNOWLEDGE BASE (REFERENCE DOCS) ===
        {base_knowledge}
        ================================================
        
        === CURRENT MARKET DATA ===
        {metrics_text}
        
        === TASK ===
        Target Property: {address}
        Based on the REFERENCE DOCS (especially the slide structures and scripts) and the MARKET DATA:
        1. Generate the 'INTERNAL_CHEAT_SHEET'.
        2. Draft the content for 'STRATEGIC_DECK' following the 6-slide structure found in the knowledge base.
        3. Use the market metrics strictly.
        """

        # 4. Llamar a Gemini
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        with st.spinner('Analizando archivos internos y mercado...'):
            response = model.generate_content(SYSTEM_PROMPT)
            
        # 5. Mostrar
        if metrics_display:
            c1, c2 = st.columns(2)
            c1.metric("Success Ratio", f"{metrics_display['success_ratio']}%")
            c2.metric("Meses Inventario", f"{metrics_display['months_inventory']}")
            
        st.markdown(response.text)