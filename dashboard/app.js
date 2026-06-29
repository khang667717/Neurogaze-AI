// SRVAS Dashboard Frontend Logic

// Determine API and WebSocket paths dynamically
const apiBase = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || window.location.protocol === 'file:'
    ? `http://localhost:8000`
    : `${window.location.protocol}//${window.location.host}`;

// Use WSS for secure connections if on HTTPS
const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const wsUrl = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || window.location.protocol === 'file:'
    ? `ws://localhost:8000/ws/dashboard`
    : `${wsProtocol}//${window.location.host}/ws/dashboard`;

const wsVideoUrl = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || window.location.protocol === 'file:'
    ? `ws://localhost:8000/ws/video_feed`
    : `${wsProtocol}//${window.location.host}/ws/video_feed`;

let socket;
let focusChart;
let streamingActive = false;   // true: đang hiển thị, false: dừng
let pollTimeout = null;
let debugFrames = 0;
let debugErrors = 0;

// Token Management
let apiToken = localStorage.getItem('srvas_api_token');
if (!apiToken) {
    const urlParams = new URLSearchParams(window.location.search);
    apiToken = urlParams.get('token');
    if (!apiToken) {
        apiToken = prompt("Please enter your SRVAS API Token:", "srvas_secure_token_123");
    }
    if (apiToken) {
        localStorage.setItem('srvas_api_token', apiToken);
    }
}

// Get references to webcam stream elements
const webcamStream = document.getElementById('webcam-stream');
const webcamPlaceholder = document.getElementById('webcam-placeholder');

// Khởi tạo trạng thái tắt camera (hiển thị placeholder)
if (webcamStream) {
    webcamStream.src = '';
    webcamStream.style.display = 'none';
    if (webcamPlaceholder) {
        webcamPlaceholder.style.display = 'flex';
    }
}

// Initialize Lucide Icons
if (window.lucide) {
    window.lucide.createIcons();
}

// Generate or Retrieve Session ID
let sessionId = localStorage.getItem('srvas_session_id');
if (!sessionId) {
    sessionId = 'sim_session_' + Math.random().toString(36).substring(2, 10);
    localStorage.setItem('srvas_session_id', sessionId);
}
console.log('Active SRVAS Session:', sessionId);

// Setup Chart.js context and linear gradient
const canvas = document.getElementById('focusChart');
const ctx = canvas.getContext('2d');
const chartGradient = ctx.createLinearGradient(0, 0, 0, 250);
chartGradient.addColorStop(0, 'rgba(59, 130, 246, 0.35)');
chartGradient.addColorStop(0.8, 'rgba(59, 130, 246, 0.05)');
chartGradient.addColorStop(1, 'rgba(59, 130, 246, 0)');

focusChart = new Chart(ctx, {
    type: 'line',
    data: {
        labels: [],
        datasets: [{
            label: 'Focus Score (%)',
            data: [],
            borderColor: '#3b82f6',
            borderWidth: 3,
            backgroundColor: chartGradient,
            pointBackgroundColor: '#3b82f6',
            pointBorderColor: 'rgba(255, 255, 255, 0.8)',
            pointHoverBackgroundColor: '#10b981',
            pointHoverBorderColor: '#fff',
            pointRadius: 4,
            pointHoverRadius: 6,
            tension: 0.35,
            fill: true
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false },
            tooltip: {
                backgroundColor: 'rgba(15, 23, 42, 0.9)',
                titleFont: { family: 'Outfit', size: 12, weight: 'bold' },
                bodyFont: { family: 'Outfit', size: 12 },
                borderColor: 'rgba(255, 255, 255, 0.1)',
                borderWidth: 1,
                padding: 10,
                cornerRadius: 8,
                displayColors: false
            }
        },
        scales: {
            x: {
                grid: { color: 'rgba(255, 255, 255, 0.05)' },
                ticks: { font: { family: 'Outfit', size: 11 }, color: 'rgba(255, 255, 255, 0.6)' }
            },
            y: {
                beginAtZero: true,
                max: 100,
                grid: { color: 'rgba(255, 255, 255, 0.05)' },
                ticks: { font: { family: 'Outfit', size: 11 }, color: 'rgba(255, 255, 255, 0.6)' }
            }
        },
        animation: { duration: 500 }
    }
});

// WebSocket Connection Management
let dashboardWsBackoff = 1000;

function connectWebSocket() {
    if (socket) {
        socket.close();
    }

    const wsEndpoint = `${wsUrl}?token=${apiToken}`;
    socket = new WebSocket(wsEndpoint);

    socket.onopen = () => {
        dashboardWsBackoff = 1000;
        console.log('WS Connection Established');
        const statusEl = document.getElementById('status');
        const statusPanel = statusEl.parentElement;
        statusEl.textContent = 'Active connection';
        statusPanel.className = 'status-panel connected';
    };

    socket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.type === 'aggregate') {
                updateDashboard(data);
            }
        } catch (e) {
            console.error('Failed to parse WebSocket message:', e);
        }
    };

    socket.onclose = () => {
        console.warn(`WS Connection Dropped, reconnecting in ${dashboardWsBackoff}ms...`);
        const statusEl = document.getElementById('status');
        const statusPanel = statusEl.parentElement;
        statusEl.textContent = 'Disconnected';
        statusPanel.className = 'status-panel disconnected';
        setTimeout(connectWebSocket, dashboardWsBackoff);
        dashboardWsBackoff = Math.min(dashboardWsBackoff * 2, 30000);
    };
}

// Update UI elements with new aggregate frame data
function updateDashboard(data) {
    // If the webcam stream is currently offline, start it (optional)
    // But we leave streaming control to user; only update stats

    const shortSession = data.session_id.length > 12
        ? data.session_id.substring(0, 10) + '...'
        : data.session_id;
    document.getElementById('session-id').textContent = shortSession;

    const focusScoreEl = document.getElementById('focus-score');
    const scoreVal = Math.round(data.focus_score);
    focusScoreEl.textContent = scoreVal + '%';

    focusScoreEl.className = 'stat-value focus-value';
    if (scoreVal >= 70) {
        focusScoreEl.classList.add('green');
    } else if (scoreVal >= 45) {
        focusScoreEl.classList.add('orange');
    } else {
        focusScoreEl.classList.add('red');
    }

    document.getElementById('active-ratio').textContent = Math.round(data.active_ratio) + '%';

    const timeLabel = new Date(data.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    focusChart.data.labels.push(timeLabel);
    focusChart.data.datasets[0].data.push(scoreVal);

    if (focusChart.data.labels.length > 15) {
        focusChart.data.labels.shift();
        focusChart.data.datasets[0].data.shift();
    }
    focusChart.update();

    const logList = document.getElementById('log-list');
    const li = document.createElement('li');
    li.className = scoreVal >= 70 ? 'focus-log' : (scoreVal >= 45 ? 'warning-log' : 'distract-log');

    const timestampSpan = document.createElement('span');
    timestampSpan.textContent = `[${timeLabel}]`;
    timestampSpan.style.opacity = '0.6';

    const textSpan = document.createElement('span');
    textSpan.textContent = `Aggregate updated - Focus: ${scoreVal}%`;
    textSpan.style.marginLeft = '8px';

    li.appendChild(timestampSpan);
    li.appendChild(textSpan);
    logList.prepend(li);

    if (logList.children.length > 12) {
        logList.removeChild(logList.lastChild);
    }
}

// Clear event logs
const btnClearLogs = document.getElementById('btn-clear-logs');
if (btnClearLogs) {
    btnClearLogs.addEventListener('click', () => {
        const logList = document.getElementById('log-list');
        if (logList) logList.innerHTML = '';
    });
}

// Simulation event injection
const btnSimFocus = document.getElementById('btn-sim-focus');
const btnSimDistract = document.getElementById('btn-sim-distract');
const simStatus = document.getElementById('sim-status');

async function sendSimulatedEvent(isFocusEvent) {
    const eventCode = isFocusEvent ? 'PERSON_DETECTED' : 'NO_PERSON';
    const cleanLabel = isFocusEvent ? 'Focus (Person Detected)' : 'Distraction (No Person)';

    try {
        simStatus.textContent = `Injecting ${eventCode}...`;
        simStatus.style.color = 'var(--accent-blue)';

        // Đảm bảo apiToken được set
        if (!apiToken) {
            throw new Error('API token not configured. Please enter token when prompted.');
        }

        const response = await fetch(`${apiBase}/api/events`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-API-Key': apiToken
            },
            body: JSON.stringify({
                event_id: 'sim_' + Math.random().toString(36).substring(2, 9),
                session_id: sessionId,
                event_code: eventCode,
                timestamp: Date.now() / 1000,
                confidence: 0.95,
                payload: {}
            })
        });

        if (response.ok) {
            simStatus.textContent = `Injected: ${cleanLabel}`;
            simStatus.style.color = isFocusEvent ? 'var(--success)' : 'var(--danger)';
            setTimeout(() => {
                simStatus.textContent = 'Ready to inject events';
                simStatus.style.color = '';
            }, 3000);
        } else {
            const errorDetail = await response.text();
            throw new Error(`Status ${response.status}: ${errorDetail}`);
        }
    } catch (error) {
        console.error('Failed to inject synthetic event:', error);
        console.log('Using token:', apiToken);
        simStatus.textContent = `Injected failed: ${error.message}`;
        simStatus.style.color = 'var(--danger)';
    }
}

if (btnSimFocus) btnSimFocus.addEventListener('click', () => sendSimulatedEvent(true));
if (btnSimDistract) btnSimDistract.addEventListener('click', () => sendSimulatedEvent(false));

// Register active session ID in DB on load
fetch(`${apiBase}/api/sessions?session_id=${sessionId}`, { method: 'POST' })
    .then(res => res.json())
    .then(data => console.log('Active session registered with DB:', data))
    .catch(err => console.warn('Could not register session via HTTP API (Backend offline?):', err));

fetch(`${apiBase}/api/dashboard`)
    .then(res => res.json())
    .then(data => console.log('Backend Status:', data))
    .catch(err => console.log('Aggregator API not reachable via HTTP'));

// Connect WebSockets
connectWebSocket();

// ========== CẢI TIẾN: START / STOP CAMERA ==========
let videoSocket = null;
let consecutiveErrors = 0;

function startWebcam() {
    if (streamingActive) return;
    streamingActive = true;
    consecutiveErrors = 0;
    console.log('Start streaming');

    const debugMsg = document.getElementById('debug-message');
    if (debugMsg) debugMsg.textContent = 'Connecting to backend video stream...';

    if (webcamStream) webcamStream.style.display = 'block';
    if (webcamPlaceholder) webcamPlaceholder.style.display = 'none';

    connectVideoSocket();
}

function stopWebcam() {
    if (!streamingActive) return;
    streamingActive = false;
    
    if (videoSocket) {
        videoSocket.close();
        videoSocket = null;
    }

    if (webcamStream && webcamStream.src && webcamStream.src.startsWith('blob:')) {
        URL.revokeObjectURL(webcamStream.src);
    }
    webcamStream.src = '';
    webcamStream.style.display = 'none';
    if (webcamPlaceholder) webcamPlaceholder.style.display = 'flex';

    const debugMsg = document.getElementById('debug-message');
    if (debugMsg) debugMsg.textContent = 'Run cv/main.py or use the simulator below';

    console.log('Stop streaming');
}

function connectVideoSocket() {
    if (!streamingActive) return;

    const videoWsEndpoint = `${wsVideoUrl}?token=${apiToken}`;
    videoSocket = new WebSocket(videoWsEndpoint);

    videoSocket.onopen = () => {
        consecutiveErrors = 0;
        updateDebugUI(true);
    };

    videoSocket.onmessage = (event) => {
        if (!streamingActive) return;
        // The event.data will be a Blob because we are receiving binary frames
        const blob = event.data;
        const url = URL.createObjectURL(blob);
        if (webcamStream.src && webcamStream.src.startsWith('blob:')) {
            URL.revokeObjectURL(webcamStream.src);
        }
        webcamStream.src = url;
        debugFrames++;
        updateDebugUI(true);
    };

    videoSocket.onclose = () => {
        if (!streamingActive) return;
        consecutiveErrors++;
        debugErrors++;
        updateDebugUI(false, "Connection lost");
        
        if (consecutiveErrors > 5) {
            const debugMsg = document.getElementById('debug-message');
            if (debugMsg) debugMsg.textContent = '⚠️ Backend unreachable. Check cv/main.py';
        }
        
        let delay = Math.min(1000 * Math.pow(2, consecutiveErrors - 1), 30000);
        console.warn(`Video WS Dropped, reconnecting in ${delay}ms...`);
        showToast("Video Connection Lost. Reconnecting...", "error");
        setTimeout(() => connectVideoSocket(), delay);
    };

    videoSocket.onerror = (err) => {
        console.error("Video WebSocket error:", err);
    };
}

function updateDebugUI(success, errorMsg) {
    const dfEl = document.getElementById('debug-frames');
    const deEl = document.getElementById('debug-errors');
    const dsEl = document.getElementById('debug-status');
    const msgEl = document.getElementById('debug-message');
    if (dfEl) dfEl.textContent = debugFrames;
    if (deEl) deEl.textContent = debugErrors;
    if (dsEl) {
        if (success) {
            dsEl.textContent = 'Active (WS Streaming)';
            dsEl.style.color = 'var(--success)';
        } else {
            dsEl.textContent = errorMsg ? `Error: ${errorMsg}` : 'Connecting...';
            dsEl.style.color = 'var(--danger)';
        }
    }
    if (msgEl && !success && consecutiveErrors > 3) {
        msgEl.textContent = '⚠️ Backend unreachable. Check cv/main.py';
    }
}

// Hàm hiển thị Toast Notification đơn giản
function showToast(message, type="info") {
    let toast = document.createElement("div");
    toast.textContent = message;
    toast.style.position = "fixed";
    toast.style.bottom = "20px";
    toast.style.right = "20px";
    toast.style.padding = "10px 20px";
    toast.style.borderRadius = "8px";
    toast.style.color = "#fff";
    toast.style.background = type === "error" ? "rgba(239, 68, 68, 0.9)" : "rgba(34, 197, 94, 0.9)";
    toast.style.backdropFilter = "blur(10px)";
    toast.style.zIndex = "9999";
    toast.style.transition = "opacity 0.5s ease";
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = "0";
        setTimeout(() => toast.remove(), 500);
    }, 3000);
}

// Gắn sự kiện cho nút START / STOP (giữ nguyên, nhưng đảm bảo không bị trùng)
const btnStart = document.getElementById('btn-start-camera');
const btnStop = document.getElementById('btn-stop-camera');
if (btnStart) btnStart.addEventListener('click', startWebcam);
if (btnStop) btnStop.addEventListener('click', stopWebcam);