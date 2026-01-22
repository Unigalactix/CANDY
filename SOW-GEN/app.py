import streamlit as st
import os
from dotenv import load_dotenv
from sow_generator import generate_sow_draft, format_sow_to_html, generate_pdf_from_html

# Load env vars
load_dotenv()

st.set_page_config(page_title="SOW Generator", layout="wide")

st.title("📄 Statement of Work (SOW) Generator")
st.markdown("Generate a professional SOW PDF: **Draft -> Edit -> Publish**")

# Sidebar Settings
st.sidebar.header("Configuration")
default_url = os.getenv("LLM_BASE_URL")
default_model = os.getenv("LLM_MODEL")

if not default_url or not default_model:
    st.error("❌ Missing required environment variables! Please check your .env file.")
    st.info("Variables needed: LLM_BASE_URL, LLM_MODEL")
    st.stop()

llm_url = st.sidebar.text_input("LLM Base URL", value=default_url)
llm_model = st.sidebar.text_input("Model Name", value=default_model)

# Template
template_path = "SOW-TEMPLATE.pdf"
if os.path.exists(template_path):
    st.sidebar.success(f"Template: {template_path}")
else:
    st.sidebar.error(f"⚠️ Template '{template_path}' missing!")

# Session State Initialization
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'draft_text' not in st.session_state:
    st.session_state.draft_text = ""
if 'pdf_bytes' not in st.session_state:
    st.session_state.pdf_bytes = None

# --- STEP 1: INPUT MOM ---
if st.session_state.step == 1:
    st.header("Step 1: Input Meeting Minutes")
    mom_text = st.text_area("Paste MOM details here:", height=300)
    
    if st.button("Generate Draft", type="primary"):
        if not mom_text:
            st.error("Please provide Meeting Minutes.")
        else:
            with st.spinner("Analyzing MOM and Generating Draft..."):
                try:
                    draft = generate_sow_draft(mom_text, llm_url, llm_model)
                    st.session_state.draft_text = draft
                    st.session_state.step = 2
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

# --- STEP 2: EDIT DRAFT ---
elif st.session_state.step == 2:
    st.header("Step 2: Review & Edit Draft")
    st.info("Edit the extracted content below before generating the final PDF.")
    
    # Text Area for Editing
    edited_text = st.text_area("SOW Draft (Markdown)", value=st.session_state.draft_text, height=600)
    
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("⬅️ Back"):
            st.session_state.step = 1
            st.rerun()
    with col2:
        if st.button("Generate Final PDF 🚀", type="primary"):
            if not os.path.exists(template_path):
                st.error("Template PDF is missing.")
            else:
                st.session_state.draft_text = edited_text # Save edits
                with st.spinner("Applying Template Formatting..."):
                    try:
                        html_content = format_sow_to_html(edited_text, template_path, llm_url, llm_model)
                        pdf_bytes = generate_pdf_from_html(html_content)
                        st.session_state.pdf_bytes = pdf_bytes
                        st.session_state.html_preview = html_content
                        st.session_state.step = 3
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

# --- STEP 3: DOWNLOAD ---
elif st.session_state.step == 3:
    st.header("Step 3: Download SOW")
    st.success("SOW Generated Successfully!")
    
    # Download Button
    st.download_button(
        label="📥 Download SOW.pdf",
        data=st.session_state.pdf_bytes,
        file_name="sow.pdf",
        mime="application/pdf"
    )
    
    with st.expander("Preview Final HTML"):
        st.markdown(st.session_state.html_preview, unsafe_allow_html=True)
    
    if st.button("Start Over"):
        st.session_state.step = 1
        st.session_state.draft_text = ""
        st.session_state.pdf_bytes = None
        st.rerun()

 
