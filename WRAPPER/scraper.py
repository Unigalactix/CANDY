import asyncio
import sys
import os
from datetime import datetime
from urllib.parse import urljoin
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re
from rapidfuzz import fuzz

async def scrape_keyword(url, keyword):
    # Setup Output
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_keyword = "".join([c if c.isalnum() else "_" for c in keyword])
    
    base_output_dir = "output"
    run_dir_name = f"{safe_keyword}_{timestamp}"
    run_dir = os.path.join(base_output_dir, run_dir_name)
    os.makedirs(run_dir, exist_ok=True)
    output_file_path = os.path.join(run_dir, "results.txt")

    print(f"\n[+] Launching Scraper (Fuzzy + Links)...")
    print(f"[+] URL: {url}")
    print(f"[+] Keyword: {keyword}")
    print(f"[+] Output Dir: {run_dir}\n")

    # Keyword Variations
    variations = [keyword]
    if " " in keyword:
        variations.extend([w for w in keyword.split() if len(w) > 3])
    
    print(f"[+] Searching for variations: {variations}")

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
            page = await context.new_page()
            
            print("[*] Navigating to page...")
            try:
                await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            except Exception as e:
                 print(f"[!] Navigation warning (continuing): {e}")

            await asyncio.sleep(3)
            
            print("[*] Content loaded. Parsing...")
            content = await page.content()
            await browser.close()
            
            soup = BeautifulSoup(content, 'html.parser')
            
            results = []
            seen = set()
            
            target_tags = ['p', 'a', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'span', 'div']
            
            print("[*] Analyzing text nodes...")
            
            for tag in soup.find_all(target_tags):
                text = tag.get_text(strip=True)
                if not text: continue
                
                clean_text = ' '.join(text.split())
                if not clean_text or clean_text in seen:
                    continue
                
                match_found = False
                matched_variant = ""
                
                for variant in variations:
                    score = fuzz.partial_ratio(variant.lower(), clean_text.lower())
                    if score >= 85:
                        match_found = True
                        matched_variant = variant
                        break
                
                if match_found:
                    seen.add(clean_text)
                    
                    # Highlight
                    try:
                        pattern = re.compile(re.escape(matched_variant), re.IGNORECASE)
                        highlighted = pattern.sub(f"[[ {matched_variant.upper()} ]]", clean_text)
                        if highlighted == clean_text:
                            highlighted = f"(Fuzzy Match: {matched_variant}) {clean_text}"
                    except:
                        highlighted = clean_text

                    # Link Extraction
                    link = None
                    if tag.name == 'a':
                        link = tag.get('href')
                    else:
                        parent_a = tag.find_parent('a')
                        if parent_a:
                            link = parent_a.get('href')
                    
                    full_link = urljoin(url, link) if link else url

                    results.append({"text": highlighted, "link": full_link})
                    if len(results) >= 20:
                        break
            
            # Save Results
            with open(output_file_path, "w", encoding="utf-8") as f:
                header = f"Scrape Results (Fuzzy + Links)\nURL: {url}\nKeyword: {keyword}\nVariations: {variations}\nTime: {timestamp}\n{'-'*40}\n\n"
                f.write(header)
                
                print(f"\n[=] FOUND {len(results)} MATCHES (Top 20):\n")
                
                if not results:
                    f.write("No matches found.")
                    print("[-] No matches found.")
                
                for i, res in enumerate(results, 1):
                    entry = f"{i}. [Link]: {res['link']}\n   [Text]: {res['text']}\n"
                    f.write(entry + "\n")
                    try:
                        scan_text = res['text']
                        print(f"{i}. {scan_text[:100]}..." if len(scan_text) > 100 else f"{i}. {scan_text}")
                    except:
                        pass
            
            print(f"\n[=] Results saved to: {output_file_path}\n")

        except Exception as e:
            print(f"[-] Error: {e}")

if __name__ == "__main__":
    url_input = input("Enter Web URL: ").strip()
    keyword_input = input("Enter Keyword: ").strip()
    
    if not url_input.startswith("http"):
        url_input = "https://" + url_input
        
    asyncio.run(scrape_keyword(url_input, keyword_input))
