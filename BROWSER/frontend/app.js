const urlBar = document.getElementById('url-bar');
const goBtn = document.getElementById('go-btn');
const toggleAgentBtn = document.getElementById('toggle-agent-btn');
const sidebar = document.getElementById('agent-sidebar');
const runAgentBtn = document.getElementById('run-agent-btn');
const instructionsEditor = document.getElementById('instructions-editor');
const logOutput = document.getElementById('log-output');
const liveStream = document.getElementById('live-stream');
const overlayMsg = document.getElementById('overlay-msg');
const statusIndicator = document.getElementById('status-indicator');
const liveIndicator = document.querySelector('.live-indicator');

let ws = null;

// --- WebSocket Connection ---
function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        log("System: Connected to Candy Cloud");
        statusIndicator.innerText = "Connected";
        statusIndicator.style.color = "#4ade80"; // Green
        runAgentBtn.disabled = false;
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === "log") {
            log(msg.data);
        } else if (msg.type === "image") {
            updateStream(msg.data);
        }
    };

    ws.onclose = () => {
        log("System: Disconnected. Retrying...");
        statusIndicator.innerText = "Disconnected";
        statusIndicator.style.color = "#ef4444"; // Red
        liveIndicator.classList.remove('active');
        runAgentBtn.disabled = true;
        setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = (err) => {
        console.error("WS Error", err);
    };
}

// --- UI Interaction ---
function log(message) {
    const line = document.createElement('div');
    line.className = 'log-entry';
    line.innerText = `> ${message}`;
    logOutput.appendChild(line);
    logOutput.scrollTop = logOutput.scrollHeight;
}

function updateStream(base64Data) {
    liveStream.src = `data:image/jpeg;base64,${base64Data}`;
    document.querySelector('.browser-view').classList.add('active');

    liveIndicator.classList.add('active');
    clearTimeout(window.streamTimeout);
    window.streamTimeout = setTimeout(() => {
        liveIndicator.classList.remove('active');
    }, 1000);
}

// Navigation Logic
function requestNavigation() {
    let url = urlBar.value.trim();
    if (!url) return;

    if (!url.startsWith('http')) {
        url = 'https://' + url;
        urlBar.value = url;
    }

    if (ws && ws.readyState === WebSocket.OPEN) {
        log(`System: Navigating to ${url}...`);
        ws.send(JSON.stringify({
            action: "navigate",
            url: url
        }));
    } else {
        log("Error: Not connected to agent.");
    }
}

urlBar.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') requestNavigation();
});

goBtn.addEventListener('click', requestNavigation);

// Sidebar Toggle
toggleAgentBtn.addEventListener('click', () => {
    sidebar.classList.toggle('collapsed');
    // If opening, focus editor? Optional.
});

// Agent Execution
runAgentBtn.addEventListener('click', () => {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;

    const instructions = instructionsEditor.value;
    log("System: Sending Agent Command Batch...");

    ws.send(JSON.stringify({
        action: "run",
        instructions: instructions
    }));
});

// Init
log("System: Initializing Candy Browser...");
connectWebSocket();
