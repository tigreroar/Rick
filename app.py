import streamlit as st
import pandas as pd
import google.generativeai as genai
import os
import pdfplumber

# --- CONFIGURATION ---
st.set_page_config(page_title="Listing Powerhouse AI (Pro)", page_icon="🏠", layout="wide")

# --- 1. KNOWLEDGE BASE MANAGEMENT (PDFs) ---
def load_knowledge_base():
    """Reads internal manuals."""
    knowledge_text = ""
    folder_path = "knowledge_base"  # Ensure your folder is named this
    
    if not os.path.exists(folder_path): return ""

    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            if filename.lower().endswith('.pdf'):
                with pdfplumber.open(file_path) as pdf:
                    text = ""
                    for page in pdf.pages:
                        extracted = page.extract_text()
                        if extracted: text += extracted + "\n"
                    knowledge_text += f"\n--- DOC: {filename} ---\n{text}\n"
            elif filename.lower().endswith(('.txt', '.md', '.csv')):
                with open(file_path, 'r', encoding='utf-8') as f:
                    knowledge_text += f"\n--- DOC: {filename} ---\n{f.read()}\n"
        except: pass
    return knowledge_text

# --- 2. ADVANCED MATH CALCULATION ('Rick' Logic) ---
def calculate_metrics(df, months_analyzed=6):
    """
    Calculates precise metrics based on the selected period (e.g., 6 or 12 months).
    """
    try:
        # 1. Clean columns
        df.columns = [c.lower().strip() for c in df.columns]
        
        # 2. Identify key columns dynamically
        status_col = next((c for c in df.columns if 'status' in c), None)
        price_col = next((c for c in df.columns if 'price' in c or 'list' in c), None)
        
        if not status_col: return "Error: 'Status' column not found."

        # 3. Aggressive "Regex" Filters to capture all data
        # Captures: Cancelled, Canceled, Withdrawn, Terminated, Expired
        sold_mask = df[status_col].str.contains('sold|closed|settled', case=False, na=False)
        exp_mask = df[status_col].str.contains('expired|term', case=False, na=False)
        fail_mask = df[status_col].str.contains('withdrawn|cancel|temp', case=False, na=False)
        active_mask = df[status_col].str.contains('active|available|coming', case=False, na=False)

        sold_count = df[sold_mask].shape[0]
        expired_count = df[exp_mask].shape[0]
        withdrawn_count = df[fail_mask].shape[0]
        active_count = df[active_mask].shape[0]

        # 4. Absorption Math (CORRECTED)
        # If analyzing 6 months, divide sales by 6, not 12.
        sales_per_month = sold_count / months_analyzed
        
        if sales_per_month > 0:
            months_inventory = active_count / sales_per_month
        else:
            months_inventory = 99.9 # Stagnant market

        # 5. Success Ratio
        total_failures = expired_count + withdrawn_count
        total_attempts = sold_count + total_failures
        success_ratio = (sold_count / total_attempts * 100) if total_attempts > 0 else 0

        # 6. Extra Data for AI
        avg_price = df[sold_mask][price_col].mean() if price_col else 0

        return {
            "sold": sold_count,
            "expired": expired_count,
            "withdrawn": withdrawn_count,
            "active": active_count,
            "success_ratio": round(success_ratio, 1),
            "months_inventory": round(months_inventory, 2),
            "avg_sold_price": f"${avg_price:,.0f}",
            "period_used": months_analyzed
        }
    except Exception as e:
        return f"Math Error: {e}"

# --- INTERFACE ---
with st.sidebar:
    st.header("⚙️ Control Panel")
    env_key = os.getenv("GOOGLE_API_KEY")
    api_key = env_key if env_key else st.text_input("API Key", type="password")
    
    st.divider()
    st.subheader("📊 Market Data")
    uploaded_file = st.file_uploader("1. Upload MLS CSV", type=["csv"])
    
    # Time Selector to fix MOI calculation
    months_analyzed = st.number_input("2. How many months does this CSV cover?", min_value=1, max_value=24, value=6, help="If you searched for sales in the last 6 months, enter 6. This fixes the Inventory calculation.")

st.title("🏠 Listing Powerhouse AI (Rick Edition)")
st.markdown("### Precision Strategy Generator")

# --- Property Inputs ---
col1, col2 = st.columns(2)
with col1:
    address = st.text_input("📍 Address:")
    style = st.text_input("🏠 Style (e.g., Colonial):")
with col2:
    details = st.text_input("📝 Key Details (Year, Lot, SqFt):", placeholder="Ex: 1994, 2.2 acres, Brick")

if st.button("🚀 Generate Strategic Analysis"):
    if not api_key:
        st.error("Missing API Key")
    else:
        # 1. Load Knowledge
        kb_text = load_knowledge_base()
        
        # 2. Process CSV with New Logic
        metrics_data = None
        metrics_str = "No market data available."
        
        if uploaded_file:
            df = pd.read_csv(uploaded_file)
            metrics_data = calculate_metrics(df, months_analyzed)
            
            if isinstance(metrics_data, dict):
                metrics_str = f"""
                === HARD MARKET DATA (Last {metrics_data['period_used']} months) ===
                - Closed Sales (Solds): {metrics_data['sold']} -> Pace: {metrics_data['sold']/months_analyzed:.1f} homes/month
                - Active (Competition): {metrics_data['active']}
                - Failed (Exp/Withdrawn): {metrics_data['expired'] + metrics_data['withdrawn']}
                
                === CRITICAL METRICS ===
                - ABSORPTION RATE (MOI): {metrics_data['months_inventory']} Months
                (Note for AI: < 3 months = Extreme Seller's Market / > 6 months = Buyer's Market)
                
                - SUCCESS RATIO: {metrics_data['success_ratio']}%
                - FAILURE RATE: {100 - metrics_data['success_ratio']:.1f}%
                - Avg Sold Price: {metrics_data['avg_sold_price']}
                """
            else:
                st.error(metrics_data)

        # 3. Engineering Prompt
        SYSTEM_PROMPT = f"""
        ACT AS: Real Estate Strategic Analyst (Code Name: Rick).
        OBJECTIVE: Create a listing strategy for Fernando Herboso.
        
        === TARGET PROPERTY ===
        Address: {address}
        Style: {style}
        Details: {details}
        
        === HARD MARKET DATA (DO NOT HALLUCINATE) ===
        {metrics_str}
        
        === KNOWLEDGE BASE ===
        {kb_text[:30000]}
        
        === INSTRUCTIONS ===
        1. **Analyze the MOI:** You see the Months of Inventory is {metrics_data['months_inventory'] if metrics_data else 'N/A'}. 
           - If < 3: Declare "EXTREME SELLER'S MARKET". Urgency is key.
           - If 3-5: Declare "BALANCED/NEUTRAL". Positioning is key.
           - If > 5: Declare "BUYER'S MARKET". Pricing is defensive.
           
        2. **Analyze Failure Rate:** Use the exact math above. If the Fail Rate is > 30%, use the script: "In this market, nearly {100 - metrics_data['success_ratio'] if metrics_data else 0:.0f}% of homes FAIL to sell."
        
        3. **Specifics:** Incorporate the property details ({style}, {details}) into the 'Description' and 'CEO Fact' script.
        
        4. **Deliverables:**
           - Internal Cheat Sheet (With the correct Math).
           - Strategic Deck Content (Slide by Slide).
        """

        # 4. Generation
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        with st.spinner('Analyzing trends and calculating absorption...'):
            try:
                response = model.generate_content(SYSTEM_PROMPT)
                
                # Data Dashboard
                if isinstance(metrics_data, dict):
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Inventory (MOI)", f"{metrics_data['months_inventory']} Months", delta_color="inverse")
                    m2.metric("Sales Probability", f"{metrics_data['success_ratio']}%")
                    m3.metric("Sales Pace", f"{metrics_data['sold']/months_analyzed:.1f} / mo")
                
                st.markdown(response.text)
            except Exception as e:
                st.error(f"Error: {e}")

