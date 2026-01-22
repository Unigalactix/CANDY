import streamlit as st
import sys
import time
import multiprocessing
import asyncio
from vanguard_simulator import run_vanguard_simulator

# Helper to redirect stdout/stderr to a queue
class QueueWriter:
    def __init__(self, queue):
        self.queue = queue
    def write(self, msg):
        if msg.strip():  # Only send non-empty messages to avoid clutter
            self.queue.put(msg)
    def flush(self):
        pass

def safe_run_process(log_queue):
    """
    Runs the simulator in a completely separate process.
    This guarantees a fresh event loop and avoids interference from Streamlit.
    """
    # 1. Force Windows Proactor Event Loop for Playwright compatibility
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    # 2. Redirect stdout/stderr to the multiprocessing queue
    sys.stdout = QueueWriter(log_queue)
    sys.stderr = QueueWriter(log_queue)

    # 3. Run the simulator
    try:
        run_vanguard_simulator()
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")

def main():
    st.set_page_config(
        page_title="Cadbury Automation",
        page_icon="🍫",
        layout="centered"
    )

    st.title("🍫 Cadbury Automation")
    st.markdown("Click below to start the **Vanguard Simulator**.")

    # Session state for logs and running status
    if "logs" not in st.session_state:
        st.session_state.logs = []
    if "running" not in st.session_state:
        st.session_state.running = False



    # Button
    if st.button("Start Process", type="primary", use_container_width=True, disabled=st.session_state.running):
        st.session_state.running = True
        st.session_state.logs = []  # Clear previous logs
        
        status_msg = st.empty()
        status_msg.info("🚀 Starting process...")

        # Create log placeholder right after button for real-time updates
        st.markdown("---")
        st.subheader("🖥️ Terminal Output")
        log_placeholder = st.empty()

        def render_logs_dynamic():
             # Build log text
            raw_logs = "".join(st.session_state.logs) if st.session_state.logs else "Waiting for process to start..."
            # Escape HTML to prevent rendering issues
            import html
            safe_logs = html.escape(raw_logs)
            
            # Update the placeholder using HTML/CSS for a terminal look
            # This avoids Streamlit's DuplicateElementKey error for widgets in loops
            log_placeholder.markdown(
                f"""
                <div style="
                    height: 600px; 
                    overflow-y: auto; 
                    background-color: #0e1117; 
                    color: #fafafa; 
                    font-family: 'Source Code Pro', monospace; 
                    font-size: 14px;
                    padding: 15px; 
                    border: 1px solid #333; 
                    border-radius: 5px; 
                    white-space: pre-wrap;
                    line-height: 1.4;
                ">{safe_logs}</div>
                """,
                unsafe_allow_html=True
            )

        # Create Queue and Process
        m = multiprocessing.Manager()
        log_queue = m.Queue()
        
        p = multiprocessing.Process(target=safe_run_process, args=(log_queue,))
        p.start()

        # Log polling loop
        while p.is_alive():
            while not log_queue.empty():
                try:
                    msg = log_queue.get_nowait()
                    st.session_state.logs.append(msg)
                except:
                    break
            
            # Update UI dynamically
            render_logs_dynamic()
            time.sleep(0.5)

        # Catch remaining logs
        while not log_queue.empty():
            try:
                msg = log_queue.get_nowait()
                st.session_state.logs.append(msg)
            except:
                break
        
        render_logs_dynamic()
        
        p.join()
        st.session_state.running = False
        
        if p.exitcode == 0:
            status_msg.success("✅ Process completed successfully!")
        else:
            status_msg.error(f"❌ Process failed with exit code {p.exitcode}")

    # If NOT running (initial state or after rerun), show logs statically
    elif st.session_state.logs:
        st.markdown("---")
        st.subheader("🖥️ Terminal Output")
        
        import html
        raw_logs = "".join(st.session_state.logs)
        safe_logs = html.escape(raw_logs)
        
        st.markdown(
            f"""
            <div style="
                height: 600px; 
                overflow-y: auto; 
                background-color: #0e1117; 
                color: #fafafa; 
                font-family: 'Source Code Pro', monospace; 
                font-size: 14px;
                padding: 15px; 
                border: 1px solid #333; 
                border-radius: 5px; 
                white-space: pre-wrap;
                line-height: 1.4;
            ">{safe_logs}</div>
            """,
            unsafe_allow_html=True
        )



if __name__ == "__main__":
    main()
