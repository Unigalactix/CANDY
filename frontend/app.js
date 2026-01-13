const termUrlArgs = document.getElementById('target-url');
const instructionsEditor = document.getElementById('instructions-editor');
const runBtn = document.getElementById('run-btn');
const logOutput = document.getElementById('log-output');
const liveStream = document.getElementById('live-stream');
const overlayMsg = document.getElementById('overlay-msg');
const statusIndicator = document.getElementById('status-indicator');
const liveDot = document.querySelector('.live-dot');

let ws = null;

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        log("System: Connected to Agent Server");
        statusIndicator.innerText = "Connected";
        statusIndicator.style.color = "#4ade80"; // Green
        runBtn.disabled = false;
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
        liveDot.classList.remove('active');
        runBtn.disabled = true;
        setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = (err) => {
        console.error("WS Error", err);
    };
}

function log(message) {
    const line = document.createElement('div');
    line.className = 'log-entry';
    line.innerText = `> ${message}`;
    logOutput.appendChild(line);
    logOutput.scrollTop = logOutput.scrollHeight;
}

function updateStream(base64Data) {
    liveStream.src = `data:image/jpeg;base64,${base64Data}`;
    liveStream.style.display = 'block';
    overlayMsg.style.display = 'none';

    // Animate dot
    liveDot.classList.add('active');

    // Clear active status after a bit if no data comes
    clearTimeout(window.streamTimeout);
    window.streamTimeout = setTimeout(() => {
        liveDot.classList.remove('active');
    }, 1000);
}

runBtn.addEventListener('click', () => {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;

    const url = termUrlArgs.value;
    const instructions = instructionsEditor.value;

    // Prepend OPEN command if not present explicitly or to ensure target
    // For this simple agent, we might want to just inject the OPEN command at the top
    let fullInstructions = instructions;
    if (url) {
        fullInstructions = `OPEN: ${url}\n` + instructions;
    }

    log("System: Sending instructions...");
    ws.send(JSON.stringify({
        action: "run",
        instructions: fullInstructions
    }));
});

// Init
log("System: Initializing Candy Client...");
connectWebSocket();
