from dotenv import load_dotenv
import os
from sow_generator import get_llm_client

load_dotenv()

try:
    client, model = get_llm_client()
    
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Hello"}],
        temperature=0.3
    )
    print("Success:")
    print(resp.choices[0].message.content)
except Exception as e:
    print("Failed:")
    print(e)
