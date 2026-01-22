"""
Streamlit UI Application for Document Processing
"""
import streamlit as st
import logging
import os
from datetime import datetime

from config import Config
from src.blob_storage import BlobStorageService
from src.document_intelligence import DocumentIntelligenceService
from src.openai_service import OpenAIService
from src.rules_validator import RulesValidator
from utils.helpers import generate_output_path, format_json_output

from utils.blob_log_handler import InMemoryLogHandler

def setup_document_logging(document_name: str) -> InMemoryLogHandler:
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Remove only existing InMemoryLogHandler instances
    for h in list(root_logger.handlers):
        if isinstance(h, InMemoryLogHandler):
            root_logger.removeHandler(h)


    handler = InMemoryLogHandler()
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    handler.setFormatter(formatter)

    root_logger.addHandler(handler)

    logging.getLogger(__name__).info(
        "Logging initialized for document: %s",
        document_name
    )

    return handler

# ============================================================
# MUST BE FIRST STREAMLIT COMMAND (ONLY ONCE)
# ============================================================
st.set_page_config(
    page_title="Vanguard Document Processing System",
    page_icon="📄",
    layout="wide"
)


# ============================================================
# CSS (UI ONLY)
# ============================================================
def load_css():
    css_path = os.path.join(
        os.path.dirname(__file__),
        "assets",
        "logo&css",
        "style.css"
    )
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


load_css()


# ============================================================
# LOGGING (UNCHANGED LOGIC)
# ============================================================
if 'logging_configured' not in st.session_state:
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True
    )
    st.session_state.logging_configured = True

logger = logging.getLogger(__name__)

logging.getLogger('azure').setLevel(logging.WARNING)
logging.getLogger('azure.core').setLevel(logging.WARNING)
logging.getLogger('azure.core.pipeline').setLevel(logging.WARNING)
logging.getLogger('azure.core.pipeline.policies').setLevel(logging.WARNING)
logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)
logging.getLogger('azure.storage').setLevel(logging.WARNING)
logging.getLogger('azure.storage.blob').setLevel(logging.WARNING)
logging.getLogger('azure.ai').setLevel(logging.WARNING)
logging.getLogger('azure.ai.documentintelligence').setLevel(logging.WARNING)

logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('src').setLevel(logging.INFO)



# Initialize session state
if 'initialized' not in st.session_state:
    st.session_state.initialized = False
    st.session_state.blob_service = None
    st.session_state.doc_intelligence_service = None
    st.session_state.openai_service = None
    st.session_state.rules_validator = None
    st.session_state.folder_list = []
    st.session_state.selected_folder = None
    st.session_state.file_list = []
    st.session_state.processing_status = None

if "last_processed_file" not in st.session_state:
    st.session_state.last_processed_file = None

if "processing_complete" not in st.session_state:
    st.session_state.processing_complete = False

if "last_result" not in st.session_state:
    st.session_state.last_result = None



def initialize_services():
    """Initialize all Azure services"""
    try:
        Config.validate()
        
        # Initialize services
        st.session_state.blob_service = BlobStorageService(
            Config.AZURE_STORAGE_CONNECTION_STRING
        )
        
        st.session_state.doc_intelligence_service = DocumentIntelligenceService(
            Config.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT,
            Config.AZURE_DOCUMENT_INTELLIGENCE_KEY
        )
        
        st.session_state.openai_service = OpenAIService(
            Config.AZURE_OPENAI_ENDPOINT,
            Config.AZURE_OPENAI_API_KEY,
            Config.AZURE_OPENAI_API_VERSION,
            Config.AZURE_OPENAI_DEPLOYMENT_NAME
        )
        
        # Initialize rules validator with blob service
        # Rules are loaded from Excel file in blob storage
        st.session_state.rules_validator = RulesValidator(
            st.session_state.blob_service,
            Config.RULES_BLOB_CONTAINER,  # Container name from .env
            Config.RULES_BLOB_FILE  # Excel file name from .env
        )
        
        st.session_state.initialized = True
        return True
        
    except ValueError as e:
        st.error(f"Configuration Error: {str(e)}")
        st.info("Please check your .env file and ensure all required variables are set.")
        return False
    except Exception as e:
        st.error(f"Error initializing services: {str(e)}")
        logger.error(f"Initialization error: {str(e)}")
        return False


def load_folder_list():
    """Load list of folders from blob storage"""
    try:
        folders = st.session_state.blob_service.list_folders(
            Config.AZURE_STORAGE_CONTAINER_NAME
        )
        st.session_state.folder_list = folders
        return folders
    except Exception as e:
        st.error(f"Error loading folder list: {str(e)}")
        logger.error(f"Error loading folders: {str(e)}")
        return []


def load_file_list(folder_name: str):
    """Load list of files from a specific folder in blob storage"""
    try:
        prefix = f"{folder_name}/" if folder_name else None
        files = st.session_state.blob_service.list_blobs(
            Config.AZURE_STORAGE_CONTAINER_NAME,
            prefix=prefix
        )
        st.session_state.file_list = files
        return files
    except Exception as e:
        st.error(f"Error loading file list: {str(e)}")
        logger.error(f"Error loading files: {str(e)}")
        return []


def process_document(file_name: str):
    """Process a selected document"""
    log_handler = setup_document_logging(file_name)
    
    try:


        logger.info("===================================================")
        logger.info("Started processing document: %s", file_name)
        logger.info("===================================================")

        with st.spinner(f"Processing {file_name}..."):
            # Step 1: Download document from blob storage
            st.info("Downloading document from blob storage...")
            logger.info("Downloading document from blob storage")

            document_bytes = st.session_state.blob_service.download_blob(
                Config.AZURE_STORAGE_CONTAINER_NAME,
                file_name
            )

            # 🔹 Store original document for download
            st.session_state.original_document_bytes = document_bytes
            st.session_state.original_document_name = file_name.split("/")[-1]


            logger.info("Document download completed (%d bytes)", len(document_bytes))

            # Step 2: Extract content using Document Intelligence
            st.info("Extracting content using Azure Document Intelligence...")
            logger.info("Starting OCR via Azure Document Intelligence")

            extracted_data = st.session_state.doc_intelligence_service.analyze_document(
                document_bytes
            )
            extracted_text = extracted_data.get("text", "")

            logger.info(
                "OCR completed. Extracted text length: %d characters",
                len(extracted_text) if extracted_text else 0
            )

            if not extracted_text:
                logger.warning("No text content extracted from the document")
                st.warning("No text content extracted from the document.")
                return None

            # Step 3: Get validation rules (optional)
            logger.info("Fetching validation rules")
            rules = st.session_state.rules_validator.get_rules()
            has_rules = rules and len(rules) > 0
            logger.info("Validation rules present: %s", has_rules)

            # Step 4: Structure and optionally validate using OpenAI
            if has_rules:
                st.info("Structuring and validating content using Azure OpenAI...")
                logger.info("Calling Azure OpenAI with validation rules")
            else:
                st.info("Structuring content using Azure OpenAI (no validation rules provided)...")
                logger.info("Calling Azure OpenAI without validation rules")

            structured_data = st.session_state.openai_service.structure_and_validate_content(
                extracted_text,
                rules if has_rules else None,
                file_name
            )

            logger.info("Azure OpenAI processing completed")

            # Clean up output - remove unwanted fields
            structured_data.pop("structured_content", None)
            structured_data.pop("validation", None)

            # Add timestamp to metadata
            if "metadata" not in structured_data:
                structured_data["metadata"] = {}
            structured_data["metadata"]["timestamp"] = datetime.now().isoformat()

            logger.info("Metadata timestamp added")

            # Step 5: Save processed data to blob storage
            st.info("Saving processed data to blob storage...")
            logger.info("Uploading structured JSON output to blob storage")

            output_path = generate_output_path(file_name)
            output_json = format_json_output(structured_data)

            st.session_state.blob_service.upload_text(
                Config.AZURE_STORAGE_OUTPUT_CONTAINER,
                output_path,
                output_json
            )

            logger.info("JSON output uploaded successfully to: %s", output_path)

            st.success(f"Document processed successfully! Saved to: {output_path}")
            logger.info("Document processing completed successfully")

            st.session_state.last_processed_file = file_name
            st.session_state.processing_complete = True
            st.session_state.last_result = structured_data

            return structured_data

    except Exception as e:
        st.error(f"Error processing document: {str(e)}")
        logger.error("Processing error occurred", exc_info=True)
        return None

    finally:
        # ------------------------------------------------------------
        # Ensure log file is flushed, detached, and uploaded
        # ------------------------------------------------------------
        if log_handler:
            try:
                logger.info("Uploading log content to blob storage")

                log_content = log_handler.get_value()

                safe_name = (
                    file_name.replace("/", "_")
                    .replace("\\", "_")
                    .replace(" ", "_")
                    .replace("(", "")
                    .replace(")", "")
                )
                log_blob_name = f"{os.path.splitext(safe_name)[0]}.log"

                st.session_state.blob_service.upload_text(
                    Config.LOG_BLOB_CONTAINER,
                    log_blob_name,
                    log_content
                )

                # 🔹 Store log blob name for download
                st.session_state.last_log_blob_name = log_blob_name


            except Exception:
                logger.error("Failed to upload log content to blob", exc_info=True)
            finally:
                # 🔹 IMPORTANT cleanup
                root_logger = logging.getLogger()
                if log_handler in root_logger.handlers:
                    root_logger.removeHandler(log_handler)


# Auto-initialize services on startup
if not st.session_state.initialized:
    with st.spinner(" Initializing services..."):
        if initialize_services():
            st.session_state.initialized = True
            st.session_state.selected_folder = "pdfestimates"
            load_file_list("pdfestimates")
        else:
            st.stop()  # Stop execution if initialization fails

# Main UI
# Header with Logo and Title
header_col1, header_col2 = st.columns([1.5, 5.5])
with header_col1:
    try:
        st.markdown("<div style='margin-top:45px'></div>", unsafe_allow_html=True)  # Adjust top margin for alignment
        # Try to load logo from assets folder - smaller size
        logo_path = os.path.join(
        os.path.dirname(__file__),
        "assets",
        "logo&css",
        "vanguard_logo.png"
    )


        if os.path.exists(logo_path):
            st.image(logo_path, width=200, output_format="PNG")
        else:
            # Alternative: try other common locations/formats
            logo_paths = [
                os.path.join(os.path.dirname(__file__), "assets", "images", "vanguard_logo.jpg"),
                os.path.join(os.path.dirname(__file__), "assets", "images", "vanguard_logo.svg"),
                os.path.join(os.path.dirname(__file__), "assets", "images", "logo.png"),
                os.path.join(os.path.dirname(__file__), "assets", "images", "logo.jpg"),
                os.path.join(os.path.dirname(__file__), "vanguard_logo.png"),
                os.path.join(os.path.dirname(__file__), "logo.png"),
            ]
            logo_found = False
            for path in logo_paths:
                if os.path.exists(path):
                    st.image(path, width=200)
                    logo_found = True
                    break
            if not logo_found:
                # Fallback: show styled title if logo not found
                st.markdown("<h2 style='color: #2E7D8A; margin-top: 0;'>VANGUARD</h2>", unsafe_allow_html=True)
    except Exception as e:
        logger.warning(f"Could not load logo: {str(e)}")
        st.markdown("<h2 style='color: #2E7D8A; margin-top: 0;'>VANGUARD</h2>", unsafe_allow_html=True)

with header_col2:
    st.markdown("<br>", unsafe_allow_html=True)  # Add some spacing
    st.markdown("<h1 style='color: #1f4e79; margin-top: 0; margin-bottom: 0.2rem;'>Document Processing System</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #666; font-size: 0.95rem; margin-top: 0;'>Powered by Azure Document Intelligence & Azure OpenAI</p>", unsafe_allow_html=True)

st.markdown("---")

# Sidebar for configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    if st.session_state.initialized:
        st.success("Services Ready")
        
        if st.button("Refresh Document List"):
            load_file_list("pdfestimates")
            st.success("Document list refreshed!")
    else:
        st.error("Services failed to initialize")
        st.info("Please check your configuration and restart the app.")

# Main content area
if st.session_state.initialized:
    # Always use pdfestimates folder
    FIXED_FOLDER = "pdfestimates"
    st.session_state.selected_folder = FIXED_FOLDER
    
    # Load files from pdfestimates folder
    if not st.session_state.file_list or st.session_state.selected_folder == FIXED_FOLDER:
        load_file_list(FIXED_FOLDER)
    
    # Document selection
    st.markdown("### 📁 Select Document")
    st.markdown("")
    
    if st.session_state.file_list:
        st.markdown("**Choose a document**")
        selected_file = st.selectbox(
            "Select a document",
            options=[""] + st.session_state.file_list,
            format_func=lambda x: "Select a document..." if x == "" else x,
            key="file_selector"
        )
        
        # 🔹 Reset ONLY if a new file is selected
        if (
            st.session_state.processing_complete
            and st.session_state.last_processed_file
            and selected_file
            and selected_file != st.session_state.last_processed_file
        ):

            st.session_state.processing_complete = False
            st.session_state.last_result = None
            st.session_state.original_document_bytes = None
            st.session_state.last_log_blob_name = None


        st.markdown("")
        
        if selected_file:
            st.markdown("")
            st.info(f" **Selected document:** {selected_file}")
            st.markdown("")
            
            st.markdown("")
            # Process button (styled green via CSS)
            if st.button("Process Document", use_container_width=True, key="process_btn"):
                process_document(selected_file)

                
            if st.session_state.processing_complete and st.session_state.last_result:
                result = st.session_state.last_result

                st.session_state.processing_status = "success"

                # Display results
                st.subheader("Processing Results")

                json_str = format_json_output(result)

                st.download_button(
                    label=" Download JSON",
                    data=json_str,
                    file_name=f"processed_{selected_file.split('/')[-1]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )

                if "original_document_bytes" in st.session_state:
                    st.download_button(
                        label=" Download Original Document",
                        data=st.session_state.original_document_bytes,
                        file_name=st.session_state.original_document_name,
                        mime="application/pdf"
                    )

                if "last_log_blob_name" in st.session_state:
                    log_bytes = st.session_state.blob_service.download_blob(
                        Config.LOG_BLOB_CONTAINER,
                        st.session_state.last_log_blob_name
                    )

                    st.download_button(
                        label=" Download Processing Log",
                        data=log_bytes,
                        file_name=st.session_state.last_log_blob_name,
                        mime="text/plain"
                    )


    else:
        st.warning(f" No documents found in folder '{FIXED_FOLDER}'.")
        if st.button(" Retry"):
            load_file_list(FIXED_FOLDER)

# Footer
st.markdown("---")
st.markdown("<div style='text-align: center; color: #666; font-size: 0.85rem; padding: 1rem 0;'>©Vanguard Document Processing System | Powered by Azure Document Intelligence & Azure OpenAI</div>", unsafe_allow_html=True)

