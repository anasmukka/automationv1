import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  Play,
  Square,
  Car,
  Images,
  ClipboardCheck,
  Terminal,
  ShieldCheck,
  Eye,
  EyeOff,
  Link as LinkIcon,
  Gauge,
} from "lucide-react";
import "./App.css";

// Use the configured backend URL when present (preview/production).
// Fall back to the local FastAPI server when running locally with no env var.
const BACKEND = process.env.REACT_APP_BACKEND_URL || "http://localhost:8001";
const API = `${BACKEND}/api`;

const PHASES = [
  { key: "trade_me_data", label: "Vehicle Info", icon: Car },
  { key: "trade_me_photos", label: "Photos", icon: Images },
  { key: "dice", label: "Dice Fill", icon: ClipboardCheck },
];

const FIELD_LABELS = [
  ["title", "Title"],
  ["price", "Price"],
  ["ask_price", "Asking Price"],
  ["year", "Year"],
  ["kilometer", "Odometer"],
  ["engine_cc", "Engine"],
  ["fuel", "Fuel"],
  ["transmission", "Transmission"],
  ["body_type", "Body Type"],
  ["doors", "Doors"],
  ["seats", "Seats"],
  ["number_plate", "Number Plate"],
  ["exterior_colour", "Exterior Colour"],
  ["import_history", "Import History"],
  ["on_road_costs", "On-road Costs"],
  ["energy_economy", "Energy Economy"],
  ["carbon_emissions", "Carbon Emissions"],
];

const RATING_LABELS = [
  ["energy_rating", "Energy Economy", "#exf_41"],
  ["overall_safety", "Overall Safety", "#exf_42"],
  ["carbon_rating", "Carbon Emissions", "#exf_43"],
  ["driver_safety", "Driver Safety", "#exf_44"],
];

function logClass(line) {
  if (line.startsWith("[ERROR]")) return "log-line err";
  if (line.startsWith("[WARNING]")) return "log-line warn";
  if (line.startsWith(">>>")) return "log-line phase";
  if (line.startsWith("[DICE]")) return "log-line dice";
  if (line.startsWith("[TRADE ME]")) return "log-line tm";
  if (line.startsWith("[PHOTO") || line.startsWith("[DOWNLOAD") || line.startsWith("[FILL]"))
    return "log-line ok";
  if (line.startsWith("[SKIP]")) return "log-line muted";
  return "log-line";
}

function StatusPill({ status }) {
  const map = {
    running: { label: "Running", cls: "pill running" },
    ready_for_review: { label: "Ready for Review", cls: "pill review" },
    completed: { label: "Completed", cls: "pill done" },
    error: { label: "Error", cls: "pill err" },
    idle: { label: "Idle", cls: "pill idle" },
  };
  const s = map[status] || map.idle;
  return <span className={s.cls} data-testid="status-pill">{s.label}</span>;
}

export default function App() {
  const [health, setHealth] = useState(null);
  const [url, setUrl] = useState("");
  const [jobId, setJobId] = useState(null);
  const [snap, setSnap] = useState(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");
  const logRef = useRef(null);
  const pollRef = useRef(null);

  useEffect(() => {
    fetch(`${API}/health`)
      .then((r) => r.json())
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  const poll = useCallback((id) => {
    fetch(`${API}/status/${id}`)
      .then((r) => r.json())
      .then((data) => {
        setSnap(data);
        if (data.done && pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [snap]);

  useEffect(() => () => pollRef.current && clearInterval(pollRef.current), []);

  const start = async () => {
    setError("");
    if (!url.trim()) {
      setError("Please paste a Trade Me listing URL.");
      return;
    }
    setStarting(true);
    try {
      const res = await fetch(`${API}/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url.trim() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to start");
      setJobId(data.job_id);
      setSnap(null);
      if (pollRef.current) clearInterval(pollRef.current);
      poll(data.job_id);
      pollRef.current = setInterval(() => poll(data.job_id), 1000);
    } catch (e) {
      setError(e.message);
    } finally {
      setStarting(false);
    }
  };

  const closeBrowser = async () => {
    if (!jobId) return;
    await fetch(`${API}/close/${jobId}`, { method: "POST" }).catch(() => {});
  };

  const status = snap?.status || "idle";
  const running = status === "running" || status === "ready_for_review";
  const currentPhase = snap?.phase;
  const phaseIndex = PHASES.findIndex((p) => p.key === currentPhase);
  const listing = snap?.listing || {};
  const ratings = snap?.ratings || {};
  const photos = snap?.photos?.urls || [];
  const logs = snap?.logs || [];

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">
            <Car size={20} />
            <span className="arrow">→</span>
            <span className="dice">DICE</span>
          </div>
          <div className="brand-text">
            <h1>Trade Me → Dice</h1>
            <p>Listing transfer automation console</p>
          </div>
        </div>
        <div className="topbar-meta">
          {health && (
            <>
              <span className={`chip ${health.headed ? "chip-on" : "chip-off"}`} data-testid="headed-chip">
                {health.headed ? <Eye size={14} /> : <EyeOff size={14} />}
                {health.headed ? "Visible browser" : "Headless"}
              </span>
              <span className={`chip ${health.dice_configured ? "chip-on" : "chip-warn"}`} data-testid="dice-chip">
                <ShieldCheck size={14} />
                {health.dice_configured ? "Dice configured" : "Dice creds not set"}
              </span>
            </>
          )}
          <StatusPill status={status} />
        </div>
      </header>

      <section className="control">
        <div className="input-wrap">
          <LinkIcon size={16} className="input-icon" />
          <input
            data-testid="url-input"
            className="url-input"
            placeholder="https://www.trademe.co.nz/a/motors/cars/.../listing/..."
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !running && start()}
            disabled={running}
          />
        </div>
        <button
          data-testid="start-btn"
          className="btn btn-start"
          onClick={start}
          disabled={running || starting}
        >
          <Play size={16} />
          {starting ? "Starting..." : "Start"}
        </button>
        <button
          data-testid="close-btn"
          className="btn btn-close"
          onClick={closeBrowser}
          disabled={status !== "ready_for_review"}
          title="Finish manual review and close the Dice browser"
        >
          <Square size={16} />
          Close Browser
        </button>
      </section>

      {error && <div className="banner err" data-testid="error-banner">{error}</div>}
      {snap?.message && (
        <div className={`banner ${status === "ready_for_review" ? "review" : status === "error" ? "err" : "info"}`} data-testid="message-banner">
          {status === "ready_for_review" && <strong>Manual review · </strong>}
          {snap.message}
        </div>
      )}

      <section className="stepper" data-testid="stepper">
        {PHASES.map((p, i) => {
          const Icon = p.icon;
          const diceSkipped =
            p.key === "dice" && snap?.done && health && !health.dice_configured;
          const state = diceSkipped
            ? "skipped"
            : phaseIndex === -1
            ? "idle"
            : i < phaseIndex || (snap?.done && i <= phaseIndex)
            ? "done"
            : i === phaseIndex
            ? "active"
            : "idle";
          return (
            <div key={p.key} className={`step ${state}`}>
              <div className="step-icon"><Icon size={18} /></div>
              <span>{diceSkipped ? "Dice Fill · Skipped" : p.label}</span>
            </div>
          );
        })}
      </section>

      <main className="grid">
        <div className="panel console-panel">
          <div className="panel-head">
            <Terminal size={16} /> Live Progress
          </div>
          <div className="console" ref={logRef} data-testid="log-console">
            {logs.length === 0 && (
              <div className="log-line muted">Waiting for a job… paste a Trade Me URL and press Start.</div>
            )}
            {logs.map((l, i) => (
              <div key={i} className={logClass(l)}>{l || "\u00A0"}</div>
            ))}
          </div>
        </div>

        <div className="side">
          <div className="panel">
            <div className="panel-head"><Gauge size={16} /> Extracted Vehicle Data</div>
            <div className="fields" data-testid="vehicle-data">
              {FIELD_LABELS.map(([key, label]) => (
                <div className="field" key={key}>
                  <span className="field-label">{label}</span>
                  <span className={`field-value ${listing[key] ? "" : "empty"}`} data-testid={`field-${key}`}>
                    {listing[key] != null && listing[key] !== "" ? String(listing[key]) : "—"}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="panel">
            <div className="panel-head"><ShieldCheck size={16} /> Trade Me Ratings</div>
            <div className="ratings" data-testid="ratings">
              {RATING_LABELS.map(([key, label, sel]) => {
                const v = ratings[key];
                return (
                  <div className="rating" key={key}>
                    <div className="rating-top">
                      <span>{label}</span>
                      <code>{sel}</code>
                    </div>
                    <span className={`rating-val ${v == null ? "none" : ""}`} data-testid={`rating-${key}`}>
                      {v == null ? "- None -" : `${v} ★`}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="panel">
            <div className="panel-head"><Images size={16} /> Gallery Photos ({photos.length})</div>
            {photos.length === 0 ? (
              <div className="empty-photos">No photos yet.</div>
            ) : (
              <div className="photo-grid" data-testid="photo-grid">
                {photos.map((src, i) => (
                  <a className="photo" href={src} target="_blank" rel="noreferrer" key={i}>
                    <img src={src} alt={`Gallery ${i + 1}`} loading="lazy" />
                    <span className="photo-idx">{i + 1}</span>
                  </a>
                ))}
              </div>
            )}
          </div>

          {snap?.description ? (
            <div className="panel">
              <div className="panel-head"><ClipboardCheck size={16} /> Description</div>
              <pre className="description" data-testid="description">{snap.description}</pre>
            </div>
          ) : null}
        </div>
      </main>

      <footer className="foot">
        <span>Safety: the automation stops before submission — it never clicks Post Ad.</span>
      </footer>
    </div>
  );
}
