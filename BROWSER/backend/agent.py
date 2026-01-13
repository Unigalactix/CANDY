import asyncio
import base64
import traceback
from playwright.async_api import async_playwright

class AsyncBrowserAgent:
    def __init__(self, browser, output_callback=None, screenshot_callback=None):
        self.browser = browser # Global browser instance
        self.output_callback = output_callback
        self.screenshot_callback = screenshot_callback
        self.context = None
        self.page = None

    async def log(self, message):
        print(f"[Agent] {message}")
        if self.output_callback:
            await self.output_callback(message)

    async def capture_screen(self):
        if self.page and self.screenshot_callback:
            try:
                if self.page.is_closed():
                    return
                # Capture as base64 for easy transport over WS
                screenshot_bytes = await self.page.screenshot(format="jpeg", quality=50)
                b64_img = base64.b64encode(screenshot_bytes).decode('utf-8')
                await self.screenshot_callback(b64_img)
            except Exception as e:
                pass

    async def start_session(self):
        """Initialize the persistent browser context/page."""
        try:
            await self.log("Starting New Browser Session...")
            self.context = await self.browser.new_context(viewport={'width': 1280, 'height': 800})
            self.page = await self.context.new_page()
            await self.log("Session Ready.")
        except Exception as e:
            await self.log(f"Failed to start session: {e}")

    async def close(self):
        """Cleanup the session."""
        if self.context:
            await self.context.close()
            await self.log("Session Closed.")

    async def navigate(self, url):
        """Direct navigation helper."""
        if not self.page:
            await self.log("Error: No active session.")
            return

        try:
            await self.log(f"Navigating to: {url}")
            await self.page.goto(url)
            await self.capture_screen()
        except Exception as e:
            await self.log(f"Navigation failed: {e}")

    async def execute(self, instructions_text):
        """Execute a batch of instructions on the CURRENT page."""
        if not self.page:
             await self.log("Error: No active session. Please restart.")
             return

        await self.log("Executing Commands...")
        
        try:
            steps = self._parse_instructions(instructions_text)
            
            for step in steps:
                cmd = step["command"]
                arg = step["args"]
                
                try:
                    if cmd == "OPEN":
                        await self.log(f"Opening: {arg}")
                        await self.page.goto(arg)
                    
                    elif cmd == "CLICK":
                        await self.log(f"Clicking: {arg}")
                        await self.page.click(arg)
                    
                    elif cmd == "TYPE":
                        if "|" in arg:
                            selector, text = arg.split("|", 1)
                            await self.log(f"Typing '{text.strip()}' into {selector.strip()}")
                            await self.page.fill(selector.strip(), text.strip())
                        else:
                            await self.log(f"Invalid TYPE format: {arg}")

                    elif cmd == "SCROLL":
                        await self.log(f"Scrolling down {arg} pixels")
                        await self.page.mouse.wheel(0, int(arg))
                    
                    elif cmd == "WAIT":
                        await self.log(f"Waiting {arg} seconds")
                        wait_time = int(arg)
                        # Capture frames frequently
                        for _ in range(wait_time * 2): 
                            await asyncio.sleep(0.5)
                            await self.capture_screen()
                        continue
                    
                    elif cmd == "EXECUTE_JS":
                        await self.log(f"Executing JS: {arg}")
                        await self.page.evaluate(arg)

                    elif cmd == "STOP":
                        await self.log("Stop condition met.")
                        break
                    
                    else:
                        await self.log(f"Unknown command: {cmd}")

                    await self.capture_screen()
                    await asyncio.sleep(0.5)

                except Exception as e:
                    await self.log(f"Error executing {cmd}: {e}")
            
            await self.log("Command Batch Finished.")
            
        except Exception as e:
            tb = traceback.format_exc()
            await self.log(f"CRITICAL AGENT ERROR:\n{tb}")
    
    def _parse_instructions(self, text):
        steps = []
        lines = text.splitlines()
        loop_buffer = []
        in_loop = False
        loop_count = 0

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"): continue
            
            parts = line.split(":", 1)
            command = parts[0].strip().upper()
            args = parts[1].strip() if len(parts) > 1 else None

            if command == "LOOP_START":
                in_loop = True
                loop_count = int(args) if args else 1
                loop_buffer = []
                continue
            
            elif command == "LOOP_END":
                if in_loop:
                    for _ in range(loop_count):
                        steps.extend(loop_buffer)
                    in_loop = False
                    loop_buffer = []
                continue

            step = {"command": command, "args": args}
            
            if in_loop:
                loop_buffer.append(step)
            else:
                steps.append(step)
        
        return steps
