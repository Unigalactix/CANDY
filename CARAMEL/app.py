import streamlit as st
import os
from dotenv import load_dotenv
from sow_generator import generate_sow_draft, format_sow_to_html, generate_merged_pdf, generate_sow_docx_bytes, convert_docx_to_pdf_bytes

# Load env vars
load_dotenv()

st.set_page_config(page_title="CARAMEL", layout="wide")

st.title("🍬 CARAMEL")
st.markdown("**(Formerly SOW-GEN)**: Generate a professional SOW PDF: **Draft -> Edit -> Publish**")

# Sidebar Settings
st.sidebar.header("Configuration")

# Check for either Standard or Azure config
has_standard = os.getenv("LLM_BASE_URL") and os.getenv("LLM_MODEL")
has_azure = os.getenv("AZURE_OPENAI_ENDPOINT") and os.getenv("AZURE_OPENAI_API_KEY")

if not (has_standard or has_azure):
    st.error("❌ Missing required environment variables! Please check your .env file.")
    st.info("Variables needed: (LLM_BASE_URL + LLM_MODEL) OR (AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY)")
    st.stop()

if has_azure:
    st.sidebar.success(f"✅ Azure OpenAI Active")
    st.sidebar.text(f"Endpoint: {os.getenv('AZURE_OPENAI_ENDPOINT')}")
else:
    llm_url = st.sidebar.text_input("LLM Base URL", value=os.getenv("LLM_BASE_URL"))
    llm_model = st.sidebar.text_input("Model Name", value=os.getenv("LLM_MODEL"))

# Template
template_path = "SOW_TEMPLATE.docx"
template_type = "docx"

if not os.path.exists(template_path):
    # Fallback/Check for legacy PDF
    if os.path.exists("SOW-TEMPLATE.pdf"):
        template_path = "SOW-TEMPLATE.pdf"
        template_type = "pdf"
        st.sidebar.warning("⚠️ Using PDF Template (DOCX Recommended)")
    else:
        st.sidebar.error("⚠️ Template 'SOW_TEMPLATE.docx' missing!")

if os.path.exists(template_path):
    st.sidebar.success(f"Template: {template_path}")

# Session State Initialization
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'draft_text' not in st.session_state:
    st.session_state.draft_text = ""
if 'output_bytes' not in st.session_state:
    st.session_state.output_bytes = None

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
                    # Config is handled internally by internal function via env vars
                    draft = generate_sow_draft(mom_text)
                    st.session_state.draft_text = draft
                    st.session_state.step = 2
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

# --- STEP 2: EDIT DRAFT ---
elif st.session_state.step == 2:
    st.header("Step 2: Review & Edit Draft")
    st.info("Edit the extracted content below before generating the final Document.")
    
    # Text Area for Editing
    edited_text = st.text_area("SOW Draft (Markdown)", value=st.session_state.draft_text, height=600)
    
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("⬅️ Back"):
            st.session_state.step = 1
            st.rerun()
    with col2:
        # User Choice for Output if DOCX
        output_format = "pdf" # Default based on user request "I WANT RESULT IN PDF"
        
        # Determine Ext based on format choice (could add a radio button in future, for now hardcoding to PDF as requested)
        ext = ".pdf"
        filename_input = st.text_input("Output Filename", value=f"SOW_Final{ext}")
        if not filename_input.lower().endswith(ext):
            filename_input += ext

        if st.button(f"Generate Final {ext.upper()} 🚀", type="primary"):
            if not os.path.exists(template_path):
                st.error("Template is missing.")
            else:
                st.session_state.draft_text = edited_text # Save edits
                with st.spinner("Applying Template & Converting..."):
                    try:
                        if template_type == "docx":
                             # 1. Generate DOCX
                             docx_bytes = generate_sow_docx_bytes(edited_text, template_path)
                             # 2. Convert to PDF
                             output = convert_docx_to_pdf_bytes(docx_bytes)
                             mime_type = "application/pdf"
                        else:
                            html_content = format_sow_to_html(edited_text, template_path)
                            output = generate_merged_pdf(html_content, template_path)
                            mime_type = "application/pdf"
                            st.session_state.html_preview = html_content
                        
                        st.session_state.output_bytes = output
                        st.session_state.output_filename = filename_input
                        st.session_state.mime_type = mime_type
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
        label=f"📥 Download {st.session_state.get('output_filename', 'sow.pdf')}",
        data=st.session_state.output_bytes,
        file_name=st.session_state.get('output_filename', 'sow.pdf'),
        mime=st.session_state.get('mime_type', "application/pdf")
    )
    
    if st.session_state.get("html_preview"):
         with st.expander("Preview Final HTML (PDF Mode Only)"):
            st.markdown(st.session_state.html_preview, unsafe_allow_html=True)
    
    if st.button("Start Over"):
        st.session_state.step = 1
        st.session_state.draft_text = ""
        st.session_state.output_bytes = None
        st.session_state.html_preview = None
        st.rerun()

 
