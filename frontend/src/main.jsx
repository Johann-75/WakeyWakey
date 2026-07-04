import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const POLL_INTERVAL_MS = 5000;
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

function formatTime(value) {
  if (!value) return "Never";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(new Date(value));
}

function formatResponseTime(value) {
  if (value === null || value === undefined) return "—";
  return `${Math.round(value)} ms`;
}

function Sparkline({ history, urlId }) {
  // Extract valid latency points (exclude null/undefined)
  const points = history
    .filter(c => c.response_time_ms !== null && c.response_time_ms !== undefined)
    .map(c => c.response_time_ms);

  if (points.length < 2) return null;

  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min;

  // Damping: If variation range is very small (<50ms), do not exaggerate color changes.
  // This keeps stable, consistent connections rendering as a uniform color theme.
  const minDampRange = 50;
  const effectiveRange = Math.max(range, minDampRange);

  // SVG dimensions
  const width = 120;
  const height = 30;
  const padding = 2;

  // Map points to SVG coordinates
  // X is distributed evenly across the width
  // Y is normalized (higher latency = peak = smaller Y in SVG coordinates)
  const svgPoints = points.map((val, index) => {
    const x = padding + (index / (points.length - 1)) * (width - 2 * padding);
    const y = height - padding - ((val - min) / (range || 1)) * (height - 2 * padding);
    return { x, y, val };
  });

  // Generate path "d" attribute: "M x0 y0 L x1 y1 ..."
  const pathD = svgPoints
    .map((p, index) => `${index === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
    .join(" ");

  // Interpolate color between green (#10b981), yellow (#eab308), and red (#ef4444)
  // to avoid muddy olive midpoints.
  const getInterpolatedColor = (val) => {
    const factor = (val - min) / effectiveRange;
    let r, g, b;
    if (factor < 0.5) {
      const segmentFactor = factor * 2;
      r = Math.round(16 + segmentFactor * (234 - 16));
      g = Math.round(185 + segmentFactor * (179 - 185));
      b = Math.round(129 + segmentFactor * (8 - 129));
    } else {
      const segmentFactor = (factor - 0.5) * 2;
      r = Math.round(234 + segmentFactor * (239 - 234));
      g = Math.round(179 + segmentFactor * (68 - 179));
      b = Math.round(8 + segmentFactor * (68 - 8));
    }
    return `rgb(${r}, ${g}, ${b})`;
  };

  // Generate gradient stops (using stable urlId instead of random floats to prevent DOM churn)
  const gradientId = `sparkline-grad-${urlId}`;
  const stops = svgPoints.map((p, index) => {
    const offset = (index / (svgPoints.length - 1)) * 100;
    const color = getInterpolatedColor(p.val);
    return <stop key={index} offset={`${offset}%`} stopColor={color} />;
  });

  return (
    <svg className="sparklineSvg" width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <defs>
        <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="0%">
          {stops}
        </linearGradient>
      </defs>
      <path
        d={pathD}
        fill="none"
        stroke={`url(#${gradientId})`}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function CheckHistoryDots({ history }) {
  if (!history || history.length === 0) {
    return <div className="historyDotsEmpty">No checks yet</div>;
  }

  // Get the is_up values for the last 5 checks
  const lastFiveIsUp = history.slice(-5).map(c => c.is_up);

  const maxDots = 5;
  const paddingCount = maxDots - lastFiveIsUp.length;
  const dots = [];

  // Add empty placeholders for checks that haven't run yet
  for (let i = 0; i < paddingCount; i++) {
    dots.push(<span key={`pad-${i}`} className="statusDotHistory placeholder" title="No check data" />);
  }

  // Add actual checks
  lastFiveIsUp.forEach((isUp, index) => {
    dots.push(
      <span
        key={`check-${index}`}
        className={`statusDotHistory ${isUp ? "up" : "down"}`}
        title={isUp ? "UP check successful" : "DOWN check failed"}
      />
    );
  });

  return <div className="historyDots">{dots}</div>;
}

function StatusBadge({ isUp }) {
  if (isUp === null || isUp === undefined) {
    return <span className="badge unknown">UNKNOWN</span>;
  }

  return (
    <span className={`badge ${isUp ? "up" : "down"}`}>
      <span className="statusDot" aria-hidden="true" />
      {isUp ? "UP" : "DOWN"}
    </span>
  );
}

function App() {
  const [urls, setUrls] = useState([]);
  const [newUrl, setNewUrl] = useState("");
  const [pollPulse, setPollPulse] = useState(false);
  const [favicon, setFavicon] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(null);
  const [error, setError] = useState("");
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem("theme") || "dark";
  });

  useEffect(() => {
    if (theme === "light") {
      document.body.classList.add("light-theme");
    } else {
      document.body.classList.remove("light-theme");
    }
    localStorage.setItem("theme", theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => prev === "dark" ? "light" : "dark");
  };

  useEffect(() => {
    if (!newUrl) {
      setFavicon(null);
      return;
    }
    const timer = setTimeout(() => {
      try {
        const parsedUrl = new URL(newUrl.startsWith("http") ? newUrl : `https://${newUrl}`);
        setFavicon(`${parsedUrl.origin}/favicon.ico`);
      } catch {
        setFavicon(null);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [newUrl]);

  const sortedUrls = useMemo(() => {
    return [...urls].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  }, [urls]);

  async function loadUrls({ quiet = false } = {}) {
    if (!quiet) setLoading(true);
    setError("");

    try {
      const response = await fetch(`${API_BASE_URL}/urls`);
      if (!response.ok) throw new Error("Could not load monitored URLs.");

      const data = await response.json();
      setUrls(data);
      setPollPulse(true);
      setTimeout(() => setPollPulse(false), 1000);
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadUrls();
    const intervalId = window.setInterval(() => {
      loadUrls({ quiet: true });
    }, POLL_INTERVAL_MS);

    return () => window.clearInterval(intervalId);
  }, []);

  async function handleSubmit(event) {
    event.preventDefault();
    const trimmedUrl = newUrl.trim();
    if (!trimmedUrl) return;

    setSaving(true);
    setError("");

    try {
      const response = await fetch(`${API_BASE_URL}/urls`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: trimmedUrl }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Could not add URL.");
      }

      setNewUrl("");
      await loadUrls({ quiet: true });
    } catch (err) {
      setError(err.message || "Could not add URL.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(urlId) {
    setDeleting(urlId);
    setError("");
    try {
      const response = await fetch(`${API_BASE_URL}/urls/${urlId}`, {
        method: "DELETE",
      });
      if (!response.ok) throw new Error("Could not delete URL.");
      await loadUrls({ quiet: true });
    } catch (err) {
      setError(err.message || "Could not delete URL.");
    } finally {
      setDeleting(null);
    }
  }

  return (
    <main className="appShell">
      <section className="topBar">
        <div>
          <h1>WakeyWakey</h1>
          <p>URL uptime monitor</p>
        </div>
        <div className="topBarRight">
          <button 
            className="themeToggle" 
            onClick={toggleTheme} 
            aria-label="Toggle dark/light theme"
          >
            {theme === "dark" ? (
              <svg className="themeIcon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="5" />
                <line x1="12" y1="1" x2="12" y2="3" />
                <line x1="12" y1="21" x2="12" y2="23" />
                <path d="M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
              </svg>
            ) : (
              <svg className="themeIcon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
              </svg>
            )}
          </button>
          <div className={`pollNote ${pollPulse ? "pulseNote" : ""}`}>Refreshes every 5s</div>
        </div>
      </section>

      <form className="addForm" onSubmit={handleSubmit}>
        <div className="inputWrapper">
          <input
            aria-label="URL"
            type="url"
            placeholder="https://example.com"
            value={newUrl}
            onChange={(event) => setNewUrl(event.target.value)}
            required
          />
          <span className="inputIcon">
            {favicon ? (
              <img
                src={favicon}
                alt="favicon"
                className="faviconIcon"
                onError={() => setFavicon(null)}
              />
            ) : (
              <svg className="globeIcon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <line x1="2" y1="12" x2="22" y2="12" />
                <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
              </svg>
            )}
          </span>
        </div>
        <button type="submit" disabled={saving}>
          {saving ? "Adding..." : "Add URL"}
        </button>
      </form>

      {error && <div className="error">{error}</div>}

      <section className="tableWrap">
        <table>
          <thead>
            <tr>
              <th>URL</th>
              <th>Status</th>
              <th>Response</th>
              <th>Last checked</th>
              <th>Recent checks</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {sortedUrls.map((item) => (
              <tr key={item.id}>
                <td className="urlCell">
                  <div className="urlContainer">
                    <span className="urlText">{item.url}</span>
                    <a 
                      href={item.url} 
                      target="_blank" 
                      rel="noopener noreferrer" 
                      className="urlRedirectLink"
                      title={`Open ${item.url} in a new tab`}
                      aria-label={`Open ${item.url} in a new tab`}
                    >
                      <svg className="redirectIcon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3" />
                      </svg>
                    </a>
                  </div>
                </td>
                <td>
                  <StatusBadge isUp={item.is_up} />
                </td>
                <td className="responseCell">
                  <span className="responseText">{formatResponseTime(item.response_time_ms)}</span>
                  <Sparkline history={[...(item.recent_checks || [])].reverse()} urlId={item.id} />
                </td>
                <td>{formatTime(item.checked_at)}</td>
                <td>
                  <CheckHistoryDots history={[...(item.recent_checks || [])].reverse()} />
                </td>
                <td>
                  <button
                    className="deleteBtn"
                    onClick={() => handleDelete(item.id)}
                    disabled={deleting === item.id}
                    aria-label={`Delete ${item.url}`}
                  >
                    {deleting === item.id ? "…" : "✕"}
                  </button>
                </td>
              </tr>
            ))}
            {!loading && sortedUrls.length === 0 && (
              <tr>
                <td className="empty" colSpan="6">
                  No URLs yet.
                </td>
              </tr>
            )}
            {loading && (
              <tr>
                <td className="empty" colSpan="6">
                  Loading...
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
