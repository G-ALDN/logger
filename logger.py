import docker # type: ignore
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import os
from fastapi import FastAPI # type: ignore
from fastapi.responses import HTMLResponse # type: ignore
from fastapi.responses import FileResponse # type: ignore
from fastapi.staticfiles import StaticFiles # type: ignore
import collections

client = docker.from_env()
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

log_buffer = collections.deque(maxlen=500)


def stream_container_logs(container):
    #Prints logs for every container
    print(f"--- Starting stream for: {container.name} ---")
    timestamp = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d %H:%M:%S")
    log_stream = container.logs(follow=True, stream=True, tail=0)
    for line in log_stream:
        clean_line = line.decode('utf-8').strip()
        log_buffer.append(f"[{timestamp}] [{container.name}] {clean_line}")
        print(f"[{timestamp}] [{container.name}] {clean_line}", flush=True)
    log_stream.close()


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

@app.get("/", response_class=FileResponse)
async def get_ui():
    return "index.html"

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