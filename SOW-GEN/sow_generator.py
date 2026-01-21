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

def generate_sow_content(mom_text, template_pdf_path, base_url="http://localhost:11434/engines/v1", model="llama3.2", api_key=None):
    """
    Generates SOW content by reading a PDF template structure and filling it with MOM details via LLM.
    Returns: Markdown/HTML text ready for PDF conversion.
    """
    # 1. Extract Template Text
    print(f"\n[+] Reading Template from {template_pdf_path}...")
    template_text = extract_text_from_pdf(template_pdf_path)
    
    # Resolving API Key
    if not api_key:
        api_key = os.getenv("LLM_API_KEY", "sow-gen")

    # 2. Connect to LLM
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

    # --- Final Generation ---
    print("[+] Generating Final SOW...")
    
    system_prompt = "You are a professional Project Manager and Technical Writer."
    user_prompt = (
        f"I have the following Consolidated Project Details (extracted from meeting minutes):\n"
        f"---------------------\n"
        f"{consolidated_info}\n"
        f"---------------------\n\n"
        f"And I have the TEXT extracted from a previous SOW PDF Template:\n"
        f"---------------------\n"
        f"{template_text}\n"
        f"---------------------\n\n"
        f"Instructions:\n"
        f"1. Create a NEW Statement of Work (SOW) based on the **structure** and **style** of the Template, but filled with the Project Details provided.\n"
        f"2. Use HTML formatting for the output (e.g., <h1>, <h2>, <p>, <ul>, <li>).\n"
        f"3. Ensure it looks professional.\n"
        f"4. Output ONLY the HTML content. Do NOT include markdown code blocks (```html)."
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
        # Strip markdown code blocks if LLM adds them despite instructions
        content = content.replace("```html", "").replace("```", "").strip()
        return content
        
    except Exception as e:
        return f"<h3>Error Generating SOW</h3><p>{str(e)}</p>"
