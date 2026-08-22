"""FastAPI backend that drives the Trade Me -> Dice automation from a web UI.

Endpoints (all under /api):
  GET  /api/health            -> service + config info
  POST /api/start             -> {url} start a job, returns {job_id}
  GET  /api/status/{job_id}   -> full progress snapshot (polled by the UI)
  POST /api/close/{job_id}    -> finish manual review / close the Dice browser

The automation uses Playwright's sync API, so each job runs in a background
thread. The final Post/Submit button is NEVER clicked.
"""

import threading
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from automation import config
from automation.runner import run_job
from automation.utils import add_log_listener, remove_log_listener

app = FastAPI(title="Trade Me -> Dice Automation")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# In-memory job store (single-user local tool -> one job at a time)
# ---------------------------------------------------------
class Job:
    def __init__(self, job_id: str, url: str):
        self.id = job_id
        self.url = url
        self.status = "running"          # running | ready_for_review | completed | error
        self.phase = "starting"
        self.phase_label = "Starting..."
        self.message = ""
        self.error = None
        self.logs: list[str] = []
        self.listing: dict | None = None
        self.description: str = ""
        self.ratings: dict | None = None
        self.photos: dict = {"urls": [], "files": []}
        self.done = False
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.close_event = threading.Event()
        self.lock = threading.Lock()

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "job_id": self.id,
                "url": self.url,
                "status": self.status,
                "phase": self.phase,
                "phase_label": self.phase_label,
                "message": self.message,
                "error": self.error,
                "logs": list(self.logs),
                "listing": self.listing,
                "description": self.description,
                "ratings": self.ratings,
                "photos": self.photos,
                "done": self.done,
                "created_at": self.created_at,
            }


_jobs: dict[str, Job] = {}
_active_lock = threading.Lock()
_active_job_id: str | None = None


def _make_emitter(job: Job):
    def emit(event: dict):
        etype = event.get("type")
        with job.lock:
            if etype == "log":
                job.logs.append(event["message"])
            elif etype == "phase":
                job.phase = event.get("phase", job.phase)
                job.phase_label = event.get("label", job.phase_label)
                job.logs.append(f">>> {job.phase_label}")
            elif etype == "data":
                job.listing = event.get("listing")
                job.description = event.get("description", "")
            elif etype == "ratings":
                job.ratings = event.get("ratings")
            elif etype == "photos":
                job.photos = {
                    "urls": event.get("urls", []),
                    "files": event.get("files", []),
                }
            elif etype == "status":
                job.status = event.get("status", job.status)
                job.message = event.get("message", "")
            elif etype == "done":
                job.done = True
    return emit


def _run(job: Job):
    emit = _make_emitter(job)

    def log_listener(message: str):
        emit({"type": "log", "message": message})

    add_log_listener(log_listener)
    try:
        run_job(job.url, emit, job.close_event)
    finally:
        remove_log_listener(log_listener)
        global _active_job_id
        with _active_lock:
            if _active_job_id == job.id:
                _active_job_id = None


# ---------------------------------------------------------
# API
# ---------------------------------------------------------
class StartRequest(BaseModel):
    url: str


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "headed": config.HEADED,
        "dice_configured": bool(config.DICE_USERNAME and config.DICE_PASSWORD),
        "dice_url": config.DICE_URL,
    }


@app.post("/api/start")
def start(req: StartRequest):
    url = (req.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="A Trade Me listing URL is required.")

    global _active_job_id
    with _active_lock:
        if _active_job_id is not None:
            active = _jobs.get(_active_job_id)
            if active and not active.done:
                raise HTTPException(
                    status_code=409,
                    detail="A job is already running. Close it before starting a new one.",
                )
        job_id = uuid.uuid4().hex[:12]
        job = Job(job_id, url)
        _jobs[job_id] = job
        _active_job_id = job_id

    thread = threading.Thread(target=_run, args=(job,), daemon=True)
    thread.start()

    return {"job_id": job_id}


@app.get("/api/status/{job_id}")
def status(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job.snapshot()


@app.post("/api/close/{job_id}")
def close(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    job.close_event.set()
    return {"ok": True}
