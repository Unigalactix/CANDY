import streamlit as st
import os
from dotenv import load_dotenv
from sow_generator import generate_sow_content, generate_pdf_from_html, extract_text_from_pdf

# Load env vars
load_dotenv()

st.set_page_config(page_title="SOW Generator", layout="wide")

st.title("📄 Statement of Work (SOW) Generator")
st.markdown("Generate a professional SOW PDF from your Meeting Minutes using a PDF Template.")

# Sidebar Settings
st.sidebar.header("Configuration")
default_url = os.getenv("LLM_BASE_URL", "http://localhost:11434/engines/v1")
default_model = os.getenv("LLM_MODEL", "llama3.2")

llm_url = st.sidebar.text_input("LLM Base URL", value=default_url)
llm_model = st.sidebar.text_input("Model Name", value=default_model)

# Main Layout
col1, col2 = st.columns(2)

with col1:
    st.header("1. Inputs")
    
    # Template
    template_path = "SOW-TEMPLATE.pdf"
    if os.path.exists(template_path):
        st.success(f"Using Default Template: {template_path}")
    else:
        st.error(f"⚠️ Default template '{template_path}' not found! Please place it in the folder.")


    # MOM Input
    st.subheader("Minutes of Meeting (MOM)")
    mom_text = st.text_area("Paste MOM details here:", height=300)

with col2:
    st.header("2. Generate")
    
    generate_btn = st.button("🚀 Generate SOW PDF", type="primary")
    
    if generate_btn:
        if not mom_text:
            st.error("Please provide Meeting Minutes.")
        elif not os.path.exists(template_path):
            st.error("Template PDF is missing.")
        else:
            with st.spinner("Analyzing Template and Generating Content via Local LLM..."):
                try:
                    # Generate Content
                    html_content = generate_sow_content(mom_text, template_path, llm_url, llm_model)
                    
                    # Convert to PDF
                    pdf_bytes = generate_pdf_from_html(html_content)
                    
                    st.success("SOW Generated Successfully!")
                    
                    # Preview (HTML)
                    with st.expander("Preview Generated Content (HTML)"):
                        st.markdown(html_content, unsafe_allow_html=True)
                    
                    # Download Button
                    st.download_button(
                        label="📥 Download SOW.pdf",
                        data=pdf_bytes,
                        file_name="sow.pdf",
                        mime="application/pdf"
                    )
                    
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")

 
