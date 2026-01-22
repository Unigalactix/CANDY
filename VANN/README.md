# AUNTY - Document Processing System

A Streamlit-based application for processing documents using Azure Document Intelligence and Azure OpenAI.

## Features

- **Document Processing**: Upload and process PDF/image documents.
- **Azure Integration**: Uses Azure Document Intelligence for OCR and Azure OpenAI for structuring data.
- **Validation**: Rules-based validation of extracted data.
- **Blob Storage**: Securely downloads input files and uploads processed results to Azure Blob Storage.

## Setup

1.  **Prerequisites**:
    -   Python 3.8+
    -   Azure subscription with Document Intelligence and OpenAI resources.

2.  **Installation**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configuration**:
    -   Ensure you have a `.env` file in this directory with the following variables:
        -   `AZURE_STORAGE_CONNECTION_STRING`
        -   `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT`
        -   `AZURE_DOCUMENT_INTELLIGENCE_KEY`
        -   `AZURE_OPENAI_ENDPOINT`
        -   `AZURE_OPENAI_API_KEY`
        -   ... (and other required config keys from `config.py`)

## Usage

Run the application:

```bash
python -m streamlit run app.py
```

Navigate to `http://localhost:8501` in your browser.
