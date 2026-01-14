import streamlit as st
import pandas as pd
import google.generativeai as genai
import os
import pdfplumber

# --- CONFIGURATION ---
st.set_page_config(page_title="Listing Powerhouse AI", page_icon="🏠", layout="wide")

# --- FUNCTION 1: LOAD KNOWLEDGE BASE (WITH PDFPLUMBER) ---
def load_knowledge_base():
    """Reads files using pdfplumber to avoid 'bbox' errors."""
    knowledge_text = ""
    folder_path = "knowledge_base"  # <--- RENAME YOUR FOLDER TO THIS
    
    if not os.path.exists(folder_path):
        return "⚠️ WARNING: The 'knowledge_base' folder does not exist."

    files_found = 0
    errors = []

    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        
        try:
            # IMPROVED PDF READING
            if filename.lower().endswith('.pdf'):
                with pdfplumber.open(file_path) as pdf:
                    text = ""
                    for page in pdf.pages:
                        extracted = page.extract_text()
                        if extracted:
                            text += extracted + "\n"
                    knowledge_text += f"\n--- DOCUMENT: {filename} ---\n{text}\n"
                    files_found += 1
            
            # TEXT/CSV READING
            elif filename.lower().endswith(('.txt', '.md', '.csv')):
                with open(file_path, 'r', encoding='utf-8') as f:
                    knowledge_text += f"\n--- DOCUMENT: {filename} ---\n{f.read()}\n"
                    files_found += 1
                    
        except Exception as e:
            errors.append(f"Error reading {filename}: {str(e)}")
            
    if errors:
        st.error(f"Read errors: {errors}")
        
    if files_found == 0:
        return "⚠️ No valid files found in /knowledge_base."
        
    return knowledge_text

# --- FUNCTION 2: MATH CALCULATIONS ---
def calculate_metrics(df):
    try:
        df.columns = [c.lower().strip() for c in df.columns]
        status_col = next((col for col in df.columns if 'status' in col), None)
        
        if not status_col: return "Error: 'Status' column not found in CSV."

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
        return f"Calculation Error: {e}"

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Settings")
    
    # API KEY VERIFICATION
    env_api_key = os.getenv("GOOGLE_API_KEY")
    if env_api_key:
        st.success(f"✅ API Key Detected (ends in ...{env_api_key[-4:]})")
        api_key = env_api_key
    else:
        st.warning("⚠️ GOOGLE_API_KEY environment variable not detected")
        api_key = st.text_input("Paste your manual API Key here:", type="password")
    
    st.divider()
    uploaded_file = st.file_uploader("Upload MLS CSV (Optional)", type=["csv"])

# --- MAIN INTERFACE ---
st.title("🏠 Listing Powerhouse AI")
address = st.text_input("📍 Property Address:")

if st.button("🚀 Generate Strategy"):
    if not api_key:
        st.error("❌ STOP! I need the API Key to work. Configure it in Railway or paste it on the left.")
    elif not address:
        st.warning("Please enter an address.")
    else:
        # 1. Load Files
        with st.spinner('Reading internal manuals (PDFs)...'):
            base_knowledge = load_knowledge_base()
        
        # 2. Process CSV
        metrics_text = "No CSV uploaded. Using generic assumptions."
        metrics_display = None
        if uploaded_file:
            df = pd.read_csv(uploaded_file)
            metrics = calculate_metrics(df)
            if isinstance(metrics, dict):
                metrics_text = str(metrics)
                metrics_display = metrics

        # 3. Prompt
        SYSTEM_PROMPT = f"""
        You are the Listing Powerhouse AI.
        
        === KNOWLEDGE BASE ===
        {base_knowledge[:50000]} 
        (Note: Content truncated if too long to fit context)
        
        === MARKET DATA ===
        {metrics_text}
        
        === INSTRUCTION ===
        Create the Strategic Game Plan for property: {address}.
        Use the Knowledge Base to structure the Slides and Cheat Sheet.
        """

        # 4. Generate
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.0-flash')
            
            with st.spinner('Consulting Gemini...'):
                response = model.generate_content(SYSTEM_PROMPT)
                
            if metrics_display:
                c1, c2 = st.columns(2)
                c1.metric("Success Ratio", f"{metrics_display['success_ratio']}%")
                c2.metric("Months Inv.", f"{metrics_display['months_inventory']}")
                
            st.markdown(response.text)
            
        except Exception as e:
            st.error(f"❌ Connection Error: {e}")
            st.info("Suggestion: Check that your API Key in Railway is correct and has no extra spaces.")

