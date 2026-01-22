import streamlit as st
import sys
import io
import contextlib
import threading
import queue
from vanguard_simulator import run_vanguard_simulator

st.set_page_config(
    page_title="Cadbury Automation",
    page_icon="🍫",
    layout="centered"
)

st.title("🍫 Cadbury Automation")
st.markdown("Click the button below to start the **Vanguard Simulator** process.")

# Create a placeholder for status messages
status_placeholder = st.empty()
log_placeholder = st.empty()

# Use Session State to manage execution status
if "running" not in st.session_state:
    st.session_state.running = False
if "logs" not in st.session_state:
    st.session_state.logs = ""

def run_simulation_in_thread(log_queue):
    """Runs the simulation in a separate thread and captures output."""
    log_stream = io.StringIO()
    try:
        with contextlib.redirect_stdout(log_stream):
            # Proactor event loop is handled internally by Playwright's sync_api
            # when running in a fresh thread without an existing loop.
            run_vanguard_simulator()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        log_queue.put(log_stream.getvalue())

if st.button("Start Process", type="primary", use_container_width=True, disabled=st.session_state.running):
    st.session_state.running = True
    status_placeholder.info("🚀 Process started... Please wait.")
    
    # Queue to get logs back from thread
    result_queue = queue.Queue()
    
    # Start thread
    t = threading.Thread(target=run_simulation_in_thread, args=(result_queue,))
    t.start()
    
    # Wait for completion (simple blocking for now, or use st.empty to poll if needed)
    with st.spinner("Running automation tasks... This may take a while."):
        t.join()
    
    # Get results
    logs = result_queue.get()
    st.session_state.logs = logs
    st.session_state.running = False
    status_placeholder.success("✅ Process completed successfully!")

# Display logs
if st.session_state.logs:
    with st.expander("View Process Logs", expanded=True):
        st.code(st.session_state.logs)

