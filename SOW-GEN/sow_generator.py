import os
from openai import OpenAI
from pypdf import PdfReader
from xhtml2pdf import pisa
from io import BytesIO

def extract_text_from_pdf(pdf_path):
    """
    Extracts text content from a PDF file.
    """
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        return f"Error reading PDF template: {str(e)}"

def generate_pdf_from_html(html_content):
    """
    Converts HTML string to PDF bytes.
    """
    result = BytesIO()
    pisa.CreatePDF(BytesIO(html_content.encode('utf-8')), result)
    return result.getvalue()


def generate_sow_draft(mom_text, base_url=None, model=None, api_key=None):
    """
    Generates a text/markdown draft of the SOW from MOM details.
    Returns: Markdown text string.
    """
    # Resolving Configuration
    if not base_url:
        base_url = os.getenv("LLM_BASE_URL")
    if not model:
        model = os.getenv("LLM_MODEL")
    if not api_key:
        api_key = os.getenv("LLM_API_KEY")
        
    if not all([base_url, model, api_key]):
        raise ValueError("Missing LLM configuration. Ensure LLM_BASE_URL, LLM_MODEL, and LLM_API_KEY are set in .env")

    # Connect to LLM
    print(f"[+] Connecting to Local LLM at {base_url}...")
    client = OpenAI(
        base_url=base_url,
        api_key=api_key
    )

    # --- Processing Logic for Large Inputs ---
    
    # helper: Chunk text
    def chunk_text(text, size=2000):
        return [text[i:i+size] for i in range(0, len(text), size)]
    
    mom_chunks = chunk_text(mom_text)
    consolidated_info = ""
    
    if len(mom_chunks) > 1:
        print(f"[+] Processing MOM in {len(mom_chunks)} batches...")
        for i, chunk in enumerate(mom_chunks, 1):
            print(f"    - Processing Batch {i}/{len(mom_chunks)}...")
            summary_prompt = (
                f"I have a section of Meeting Minutes. Extract key project details (Scope, Timeline, Budget, Team, Deliverables, etc.) as concise bullet points.\n"
                f"Ignore conversational filler.\n\n"
                f"MOM Segment:\n"
                f"{chunk}"
            )
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": summary_prompt}],
                    temperature=0.3
                )
                consolidated_info += f"\n--- Batch {i} Details ---\n{resp.choices[0].message.content}\n"
            except Exception as e:
                consolidated_info += f"\n[Error extracting Batch {i}: {str(e)}]\n"
    else:
        consolidated_info = mom_text

    # --- Draft Generation ---
    print("[+] Generating SOW Draft...")
    
    system_prompt = "You are a professional Project Manager and Technical Writer."
    user_prompt = (
        f"I have the following Consolidated Project Details (extracted from meeting minutes):\n"
        f"---------------------\n"
        f"{consolidated_info}\n"
        f"---------------------\n\n"
        f"Instructions:\n"
        f"1. Create a detailed Statement of Work (SOW) draft.\n"
        f"2. Use Markdown formatting (## Headers, - Bullet points).\n"
        f"3. Include standard SOW sections: Project Overview, Scope of Work, Deliverables, Timeline, Pricing/Budget, Governance/Team.\n"
        f"4. Do NOT use HTML tags yet. Just structure the content clearly.\n"
    )
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
        )
        content = response.choices[0].message.content
        return content
        
    except Exception as e:
        return f"Error Generating SOW Draft: {str(e)}"

def format_sow_to_html(edited_text, template_pdf_path, base_url=None, model=None, api_key=None):
    """
    Takes the edited SOW text and wraps it in the HTML structure of the template PDF.
    """
    if not base_url:
        base_url = os.getenv("LLM_BASE_URL")
    if not model:
        model = os.getenv("LLM_MODEL")
    if not api_key:
        api_key = os.getenv("LLM_API_KEY")

    if not all([base_url, model, api_key]):
        return "<h3>Error: Missing Configuration</h3><p>Ensure LLM env vars are set.</p>"
    
    client = OpenAI(base_url=base_url, api_key=api_key)
    
    # 1. Extract Template Text
    print(f"\n[+] Reading Template from {template_pdf_path}...")
    template_text = extract_text_from_pdf(template_pdf_path)
    
    # 2. Generate HTML
    print("[+] Applying Template Formatting...")
    
    system_prompt = "You are a specialized document formatter."
    user_prompt = (
        f"I have the final SOW Content (Markdown):\n"
        f"---------------------\n"
        f"{edited_text}\n"
        f"---------------------\n\n"
        f"And the Style/Structure extracted from a Reference PDF via OCR/Text Extraction:\n"
        f"---------------------\n"
        f"{template_text}\n"
        f"---------------------\n\n"
        f"Instructions:\n"
        f"1. Convert the 'SOW Content' into an HTML document.\n"
        f"2. Mimic the structure and specific standard clauses found in the 'Reference PDF' where applicable, but keep the specific project details from 'SOW Content'.\n"
        f"3. Use HTML tags (<h1>, <p>, <ul> etc.).\n"
        f"4. Output ONLY the valid HTML. Do not include markdown code blocks.\n"
    )
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1, # Low temp for strict formatting
        )
        content = response.choices[0].message.content
        content = content.replace("```html", "").replace("```", "").strip()
        return content
    except Exception as e:
        return f"<h3>Error Formatting SOW</h3><p>{str(e)}</p>"
