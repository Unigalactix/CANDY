from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import asyncio
import json
import os
from contextlib import asynccontextmanager
from playwright.async_api import async_playwright

# Import the agent
from .agent import AsyncBrowserAgent

# Global state
app_state = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Launch Playwright and Browser
    print("--- STARTUP: Launching Global Browser ---")
    playwright = await async_playwright().start()
    # headless=True is cleaner, ensure we use a context with viewport
    browser = await playwright.chromium.launch(headless=True)
    
    app_state["playwright"] = playwright
    app_state["browser"] = browser
    
    yield
    
    # Shutdown: Clean up
    print("--- SHUTDOWN: Closing Global Browser ---")
    await browser.close()
    await playwright.stop()

app = FastAPI(lifespan=lifespan)

# Mount frontend static files
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) # .../backend
ROOT_DIR = os.path.dirname(BASE_DIR) # .../CANDY
FRONTEND_DIR = os.path.join(ROOT_DIR, 'frontend')

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
async def read_root():
    return FileResponse(os.path.join(FRONTEND_DIR, 'index.html'))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    async def send_log(msg):
        try:
            await websocket.send_json({"type": "log", "data": msg})
        except:
            pass 

    async def send_screenshot(b64_data):
        try:
            await websocket.send_json({"type": "image", "data": b64_data})
        except:
            pass

    browser = app_state.get("browser")
    if not browser:
        await send_log("CRITICAL ERROR: Global Browser not initialized.")
        await websocket.close()
        return

    # Instantiate Agent and Start Session
    agent = AsyncBrowserAgent(browser, output_callback=send_log, screenshot_callback=send_screenshot)
    await agent.start_session()

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            action = message.get("action")
            
            if action == "navigate":
                url = message.get("url")
                await agent.navigate(url)
            
            elif action == "run":
                instructions = message.get("instructions")
                await agent.execute(instructions)
                
    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"WebSocket Error: {e}")
    finally:
        # Cleanup session on disconnect
        await agent.close()
