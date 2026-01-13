# 🕸️ Wrapper Scraper

A persistent, Python-based CLI tool to scrape top results from any website based on a keyword.
Includes **Fuzzy Logic** to find variations of your keyword (e.g., "The Rajasaab" finds "Rajasaab").

## 🚀 Features
- **Headless Browser**: Uses Playwright to render dynamic JS content (React, Angular, etc.).
- **Fuzzy Search**: Powered by `rapidfuzz` to handle typos and variations.
- **Auto-Expansion**: Automatically searches for individual significant words in a phrase.
- **Auto-Logging**: Saves every run to `output/<keyword>_<timestamp>/results.txt`.

## 📦 Installation

```bash
cd WRAPPER
pip install -r requirements.txt
playwright install
```

## 🏃 Usage

```bash
python scraper.py
```

1. Enter the **URL** (e.g., `https://www.reddit.com`).
2. Enter the **Keyword** (e.g., `The Rajasaab`).

## 📂 Output

Results are saved automatically:
`WRAPPER/output/The_Rajasaab_20260113_.../results.txt`
