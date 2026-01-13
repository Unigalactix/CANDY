# 🍬 Candy Browser Agent

**Candy Browser** is a web-based, AI-ready browser automation tool. It allows you to write natural-style instructions (or use an LLM to generate them) and watch a "Low-Key" agent execute them in real-time via a premium web interface.

![Candy Browser Interface](https://via.placeholder.com/800x400?text=Candy+Browser+UI)

## 🚀 Features

- **Live Streaming**: Watch the headless browser execute tasks in real-time via WebSocket.
- **Natural Instructions**: Simple text-based command format (`OPEN`, `CLICK`, `TYPE`, `SCROLL`).
- **Premium UI**: Dark-mode, Glassmorphism design with responsive feedback.
- **Robust Backend**: Powered by FastAPI and Async Playwright.
- **Global Browser Instance**: Efficient resource management for stability.

## 🛠️ Tech Stack

- **Backend**: Python (FastAPI, Uvicorn)
- **Automation**: Playwright (Async API)
- **Frontend**: Vanilla HTML5, CSS3, JavaScript (No build tools required)
- **Protocol**: WebSockets (JSON + Base64 Image Streaming)

## 📦 Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/yourusername/candy-browser.git
    cd candy-browser
    ```

2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    playwright install
    ```

## 🚦 Usage

1.  **Start the Server**:
    Double-click `run_browser_agent.bat` OR run:
    ```bash
    python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
    ```

2.  **Open the App**:
    Navigate to [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

3.  **Run an Agent Task**:
    - Enter a URL (e.g., `https://en.wikipedia.org/wiki/Main_Page`).
    - Use the built-in instructions example or write your own:
      ```text
      OPEN: https://www.linkedin.com/feed/
      WAIT: 5
      SCROLL: 500
      STOP:
      ```
    - Click **LAUNCH AGENT**.

## 📝 Instruction Syntax

| Command | Usage | Description |
| :--- | :--- | :--- |
| `OPEN` | `OPEN: https://url.com` | Navigates to a URL. |
| `CLICK` | `CLICK: selector` | Clicks an element matching the CSS selector. |
| `TYPE` | `TYPE: selector \| text` | Types text into an input field. |
| `SCROLL`| `SCROLL: pixels` | Scrolls down by N pixels. |
| `WAIT` | `WAIT: seconds` | Pauses execution (keeps streaming). |
| `EXECUTE_JS` | `EXECUTE_JS: code` | Runs arbitrary JavaScript on the page. |
| `STOP` | `STOP:` | Ends the agent task immediately. |

## 📄 License

MIT
