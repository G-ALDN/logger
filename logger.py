import docker
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import collections

client = docker.from_env()
app = FastAPI()

log_buffer = collections.deque(maxlen=100)


def stream_container_logs(container):
	#Prints logs for every container
	print(f"--- Starting stream for: {container.name} ---")
	timestamp = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d %H:%M:%S")

	log_stream = container.logs(follow=True, stream=True, tail=0)

	for line in log_stream:
		clean_line = line.decode('utf-8').strip()
		log_buffer.append(f"[{timestamp}] [{container.name}] {clean_line}")
		print(f"[{timestamp}] [{container.name}] {clean_line}", flush=True)


def start_logging():
	# Grab Running Containers
	containers = client.containers.list()
	self_id = os.environ.get('HOSTNAME')
	for container in containers:
		if container.id.startswith(self_id):
			print(f"Skipping self ({container.name}) to prevent log loop.")
			continue
        #Logging thread
		thread = threading.Thread(target=stream_container_logs, args=(container,), daemon=True)
		thread.start()
    #Event Thread
	e_thread = threading.Thread(target=monitor_events, daemon=True)
	e_thread.start()
	while True:
		time.sleep(1)

def monitor_events():
    """
    Listens for container start/stop events and reacts.
    """
    # Filters ensure we only wake up for specific actions
    filters = {"type": "container", "event": ["start", "die"]}
    
    # This loop blocks and waits for the next event
    for event in client.events(decode=True, filters=filters):
        container_id = event['id']
        action = event.get('action') or event.get('status')
        
        try:
            container = client.containers.get(container_id)
            if container.id.startswith(os.environ.get('HOSTNAME', 'unknown')):
                continue

            if action == "start":
                log_buffer.append(f"--- New Container Detected: {container.name} ---")
                print(f"--- New Container Detected: {container.name} ---")
                thread = threading.Thread(
                    target=stream_container_logs, 
                    args=(container,), 
                    daemon=True
                )
                thread.start()
            elif action == "die":
                log_buffer.append(f"--- Container Stopped: {container.name} ---")
                print(f"--- Container Stopped: {container.name} ---")
        except docker.errors.NotFound:
            continue

@app.get("/", response_class=HTMLResponse)
async def get_ui():
    return """
    <html>
        <head>
            <title>Log Manager</title>
            <style>
                body { font-family: 'Cascadia Code', monospace; background: #0d1117; color: #c9d1d9; margin: 0; display: flex; flex-direction: column; height: 100vh; }
                .header { background: #161b22; padding: 15px; border-bottom: 1px solid #30363d; display: flex; align-items: center; gap: 20px; }
                #search { padding: 8px; background: #0d1117; border: 1px solid #30363d; color: white; border-radius: 6px; flex-grow: 1; max-width: 400px; }
                .clear-btn { padding: 8px 15px; background: #da3633; border: none; color: white; cursor: pointer; border-radius: 6px; font-weight: bold; }
                .filters { background: #161b22; padding: 10px 15px; display: flex; gap: 10px; overflow-x: auto; border-bottom: 1px solid #30363d; }
                .filter-btn { padding: 5px 12px; background: #21262d; border: 1px solid #30363d; color: #8b949e; cursor: pointer; border-radius: 20px; white-space: nowrap; }
                .filter-btn.active { background: #238636; color: white; border-color: #2ea043; }
                #log-container { flex-grow: 1; overflow-y: auto; padding: 15px; line-height: 1.6; }
                .log-line { border-bottom: 1px solid #21262d; padding: 4px 0; font-size: 13px; }
                .timestamp { color: #58a6ff; margin-right: 10px; }
                .tag { color: #aff5b4; font-weight: bold; margin-right: 10px; }
            </style>
        </head>
        <body>
            <div class="header">
                <input type="text" id="search" placeholder="Filter logs..." oninput="applyFilters()">
                <button class="clear-btn" onclick="clearLogs()">Clear Screen</button>
            </div>
            <div class="filters" id="filter-bar">
                <button class="filter-btn active" onclick="setFilter('all')">all-containers</button>
            </div>
            <div id="log-container"></div>

            <script>
                let currentFilter = 'all';
                let allLogs = [];

                let clearPoint = 0; 

				async function clearLogs() {
					// Set the clear point to the current number of logs
					clearPoint = allLogs.length;
					applyFilters();
				}
                
                function setFilter(name) {
                    currentFilter = name;
                    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                    event.target.classList.add('active');
                    applyFilters();
                }

				function applyFilters() {
					const search = document.getElementById('search').value.toLowerCase();
					const container = document.getElementById('log-container');
					
					// Slice the array to only show logs AFTER the clear point
					const viewableLogs = allLogs.slice(clearPoint);

					const html = viewableLogs.filter(line => {
						return (currentFilter === 'all' || line.includes(`[${currentFilter}]`)) &&
							line.toLowerCase().includes(search);
					}).map(line => {
						let formatted = line.replace(/^(\[.*?\]) (\[.*?\])/, 
							'<span class="timestamp">$1</span><span class="tag">$2</span>');
						return `<div class="log-line">${formatted}</div>`;
					}).join('');

					container.innerHTML = html;
					container.scrollTop = container.scrollHeight;
				}

                async function refreshLogs() {
					const res = await fetch('/raw-logs');
					const newLogs = await res.json();
					
					// If the server buffer was cleared or rotated heavily
					if (newLogs.length < allLogs.length) {
						clearPoint = 0;
					}
					
					allLogs = newLogs;
					applyFilters();
				}

                async function loadFilters() {
                    const res = await fetch('/containers');
                    const names = await res.json();
                    const bar = document.getElementById('filter-bar');
                    names.forEach(name => {
                        const btn = document.createElement('button');
                        btn.className = 'filter-btn';
                        btn.innerText = name;
                        btn.onclick = (e) => {
                            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                            e.target.classList.add('active');
                            currentFilter = name;
                            applyFilters();
                        };
                        bar.appendChild(btn);
                    });
                }

                loadFilters();
                setInterval(refreshLogs, 1000);
            </script>
        </body>
    </html>
    """
@app.get("/containers")
async def get_containers():
    # Returns a simple list of names for our filter buttons
    return [c.name for c in client.containers.list() if not c.id.startswith(os.environ.get('HOSTNAME', ''))]
@app.get("/raw-logs")
async def get_raw_logs():
    # Returns the current log_buffer as a JSON list
    return list(log_buffer)
@app.on_event("startup")
def startup_event():
    threading.Thread(target=start_logging, daemon=True).start()
