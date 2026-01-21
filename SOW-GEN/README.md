# SOW-GEN

A Streamlit-based tool to generate **Statement of Work (SOW)** PDFs using a Local LLM.

## Features
- **PDF Template Support**: Uses `SOW-TEMPLATE.pdf` as the base structure.
- **Local LLM Integration**: Connects to Ollama/LM Studio (default: `llama3.2`).
- **Smart Chunking**: Automatically splits large inputs to fit context limits.
- **PDF Output**: Generates clean, professional PDF documents.

## Setup

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configuration**
   Copy `.env.template` to `.env` and adjust settings if needed:
   ```bash
   cp .env.template .env
   ```
   *Default connects to `http://localhost:11434/engines/v1`.*

3. **Template**
   Ensure `SOW-TEMPLATE.pdf` is present in this directory.

## Usage

Run the app:
```bash
python -m streamlit run app.py
```

Paste your **Minutes of Meeting (MOM)** into the text area and click **Generate**.
