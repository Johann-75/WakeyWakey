# WakeyWakey: URL Uptime Monitor

A simple, full-stack app that checks if your registered websites are working (UP or DOWN) and displays their response times on a live dashboard.

---

## 🚀 Setup

To spin up the entire ecosystem (both frontend and backend containers) locally, run this command from the root directory:

```bash
docker compose up --build
```

- **Frontend Dashboard**: [http://localhost/](http://localhost/)
- **Backend Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Backend Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

## 🧪 Testing Steps

To verify that the monitor correctly detects both "UP" and "DOWN" states, follow these steps:

1. Open the dashboard at [http://localhost/](http://localhost/).
2. **Test a Healthy URL (UP)**:
   - In the input field, add: `https://httpbin.org/status/200` (or `https://example.com`).
   - Click **Add URL**.
   - The dashboard will show the URL status as **UP** with a green badge and response time in milliseconds.
3. **Test an Unhealthy/Invalid URL (DOWN)**:
   - Add a failing status URL: `https://httpbin.org/status/500`.
   - Add an invalid/non-existent URL: `https://invalid-domain-does-not-exist-12345.com`.
   - The dashboard will show the status as **DOWN** with a red badge.
4. **Observe Background Polling**:
   - The backend checks all URLs every **60 seconds**.
   - The frontend refreshes every **5 seconds** to fetch updates.
   - The "Recent checks" dot row will update to show the timeline sequence of the last 5 check statuses (green dots for success, red dots for failure, and gray dashes for empty slots).
5. **Persistence**:
   - Restart the containers (`docker compose down` then `docker compose up`).
   - The registered URLs and check logs will persist, as they are saved in a SQLite database inside a named volume (`wakeywakey_sqlite_data`).

---

## ☁️ Deployment

### Live Production Deployment
*   **Frontend Dashboard (Vercel)**: [https://wakey-wakey-nine.vercel.app/](https://wakey-wakey-nine.vercel.app/)
*   **Backend API (Railway)**: [https://wakeywakey-production.up.railway.app/](https://wakeywakey-production.up.railway.app/)
    *   API Health Endpoint: [https://wakeywakey-production.up.railway.app/health](https://wakeywakey-production.up.railway.app/health)
    *   API Interactive Swagger Documentation: [https://wakeywakey-production.up.railway.app/docs](https://wakeywakey-production.up.railway.app/docs)

### Target MVP Deployment Stack
The application is designed to be easily deployed to a cloud provider using a serverless frontend + persistent backend process:

*   **Hosting Stack**:
    *   **Frontend**: Deployed on **Vercel** as a static single-page app (built from the `/frontend` root directory).
    *   **Backend**: Deployed on **Render** as a Web Service. A persistent process (like Render) is selected over stateless serverless functions (like Render Functions) to keep the background ping scheduler running continuously.
    *   **Database**: Local SQLite (self-cleaning via daily container restarts)
*   **Environment Variables**:
    *   **Backend**:
        *   `CHECK_INTERVAL_SECONDS`: The interval (in seconds) between background pings (default: `60`).
        *   `REQUEST_TIMEOUT_SECONDS`: The timeout limit (in seconds) for outgoing HTTP requests (default: `10`).
        *   `MAX_CONCURRENT_CHECKS`: The limit for concurrent outgoing HTTP check connections (default: `20`).
    *   **Frontend**: `VITE_API_BASE_URL` (the backend API URL).

---

### Scaling to Production (Hypothetical)
If this application needed to scale further, we'd recommend deploying the containerized backend to **Google Cloud Run** and serving the frontend statically via **Firebase Hosting** or **Cloud Storage + Cloud CDN**. 

Key architectural points to consider:

* **Production Storage & Serverless Inconsistency**:
  - Serverless hosting (like Google Cloud Run) is stateless, which means SQLite database files will get wiped every time the server restarts. To solve this in production, we switch to a managed PostgreSQL database (like Cloud SQL) and pass the connection details safely at runtime.

* **Build-Time Environment Variable Warning**:
  - Vite hardcodes the backend address (`VITE_API_BASE_URL`) into the static website files when it builds. This means you cannot change this address after the frontend is compiled. In production, we avoid this by routing requests through a web server proxy (like Nginx) at a relative `/api` path.

Here is a hypothetical **Terraform** snippet outlining the backend Cloud Run service deployment:

```hcl
# Serverless Cloud Run service for the Backend API
resource "google_cloud_run_service" "backend" {
  name     = "wakeywakey-backend"
  location = "us-central1"

  template {
    spec {
      containers {
        image = "gcr.io/wakeywakey-production/backend:latest"
        
        env {
          name  = "DATABASE_URL" # Injected production DB connection string
          value = "postgresql://dbuser:dbpassword@10.0.0.5/wakeywakey"
        }
        
        ports {
          container_port = 8000
        }
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }
}
```

---

## 🛠️ Repository Structure

```
WakeyWakey/
├── backend/                  # FastAPI Python API (ping scheduler + CRUD)
│   ├── main.py               # App entrypoint, routes, APScheduler lifespan
│   ├── models.py             # SQLAlchemy ORM models (Url, Check)
│   ├── schemas.py            # Pydantic request/response schemas
│   ├── database.py           # SQLite engine + session factory
│   ├── requirements.txt      # Python dependencies
│   └── Dockerfile            # python:3.11-slim image
│
├── frontend/                 # React + Vite SPA dashboard
│   ├── src/
│   │   ├── main.jsx          # App component with polling + form + table
│   │   └── styles.css        # Premium dark-mode CSS
│   ├── index.html
│   ├── nginx.conf            # Nginx SPA routing config
│   ├── Dockerfile            # Multi-stage: node build → nginx serve
│   └── package.json
│
├── docker-compose.yml        # Orchestrates backend + frontend + SQLite volume
├── README.md                 # Setup, testing steps, deployment sketch
└── AI_LOG.md                 # AI collaboration log (prompts + course corrections)
```

