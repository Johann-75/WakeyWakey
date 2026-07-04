# AI Collaboration Log

This log documents the collaboration between the developer and the AI coding assistant (**Antigravity**, powered by **Gemini 3.5 Flash** and developed by **Google DeepMind**) to build and containerize the WakeyWakey URL Uptime Monitor.

---

## 🛠️ The AI Tech Stack

- **AI Assistant**: Antigravity (Google DeepMind agentic coding assistant)
- **Large Language Model (LLM)**: Gemini 3.5 Flash (Medium)
- **Local Environment**: Windows 11 PowerShell terminal, Python 3.11, Node.js v24

---

## 💬 The Prompts that Shipped It

Here is the chronological sequence of prompts used to build, schedule, display, run, and containerize the application:

### 📑 Phase 1: Backend MVP
*   **Prompt**:
    ```text
    Build a FastAPI backend for a URL uptime monitor MVP.

    - SQLite via SQLAlchemy (file path via env var DB_PATH, default ./data/monitor.db)
    - Tables:
      - urls: id (pk), url (str, unique), created_at (datetime)
      - checks: id (pk), url_id (fk), status_code (int, nullable), response_time_ms (float, nullable), is_up (bool), checked_at (datetime)
    - Endpoints:
      - POST /urls -> {"url": "..."}
      - GET /urls -> list all URLs with latest check joined in (status_code, response_time_ms, is_up, checked_at)
      - GET /urls/{id}/checks -> history, most recent first
      - DELETE /urls/{id}
      - GET /health
    - Pydantic schemas for request/response
    - Flat structure: main.py, database.py, models.py, schemas.py
    - CORS enabled for all origins (dev only)
    - Dependencies only: fastapi, uvicorn, sqlalchemy, httpx, apscheduler

    Test each endpoint with curl after building.
    ```

### ⏰ Phase 2: Scheduler
*   **Prompt**:
    ```text
    Phase 2 — Scheduler:
    Add APScheduler job, runs every 60s:
    - Fetch all URLs, check concurrently via asyncio.gather (httpx, timeout=10s)
    - Measure elapsed time with time.perf_counter()
    - is_up = true if status 200-399, false otherwise (including timeout/connection error, status_code=null in that case)
    - Insert one checks row per URL per cycle
    - Start scheduler in FastAPI lifespan startup event
    ```

### 💻 Phase 3: Frontend (polling)
*   **Prompt**:
    ```text
    Phase 3 — Frontend (polling):
    React (Vite) frontend.
    - On mount and every 5s: GET /urls, update state
    - Form to add URL (POST /urls)
    - Table: url, status badge (🟢 UP / 🔴 DOWN), response time ms, last checked, mini success-rate indicator from last 20 checks (fetch /urls/{id}/checks, compute % is_up)
    - Minimal CSS, no component library
    ```

### 🚀 Phase 4: Starting the Dev Servers
*   **Prompt**: `"run the app na"`
*   **Action**: The AI resolved Node/Python requirements locally, ran the FastAPI backend via Uvicorn, and spun up the Vite dev server.

### 🐳 Phase 5: Containerization & Audit
*   **Prompt**: `"now bro i want u to implement Dockerfile for backend (python slim, uvicorn), Dockerfile for frontend (node build -> serve via nginx or vite preview), docker-compose.yml with backend, frontend, and a named volume for SQLite data. Single command: docker compose up., also bro can u check tht assignment pdf to see whether our app satisfies exactly what is meant to be done?"`
*   **Action**: The AI audited requirements from the assignment PDF, generated the Docker files, wrote Nginx routing rules, set up the Docker Compose named volumes, and upgraded the CSS styling to a high-fidelity dark mode with micro-animations.

---

## 🔄 The Course Corrections

During development, several adjustments and optimizations were made:

1. **Port binding inside Docker**:
   - *Issue*: Initially, the backend was configured to run on `127.0.0.1:8000` locally. However, when run inside a Docker container, binding to `127.0.0.1` restricts access to local-to-container traffic only, preventing the frontend (running on the host browser) from talking to the API.
   - *Correction*: The AI corrected this in the `Dockerfile` by binding the uvicorn command to host `0.0.0.0` (`CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]`), making the port accessible outside the container context.

2. **API Base URL configuration**:
   - *Issue*: The frontend needs to talk to the backend, but hardcoding `http://127.0.0.1:8000` is fragile in containerized environments.
   - *Correction*: The AI implemented an `ARG VITE_API_BASE_URL` in the frontend Dockerfile. This allows the API address to be dynamically configured at build time (defaulting to `http://localhost:8000`), which ensures the browser can communicate with the backend regardless of deployment host port configurations.

3. **Delete URL UI Integration**:
   - *Issue*: The backend had a `/urls/{id}` DELETE endpoint, but the frontend did not provide any UI control or button to invoke it.
   - *Correction*: Added a Delete Button column to the table in `main.jsx` and styled it as a subtle red cross (`✕`) that scales and glows on hover.

4. **Checks History Dot Row Upgrade**:
   - *Issue*: The original progress bar indicating success rate was abstract and did not clearly illustrate flakiness over time versus recent service recovery.
   - *Correction*: Replaced it with a chronological dot timeline (5 dots, oldest on the left, newest on the right) using emerald green status glows for success, red glows for failure, and dashed circles for empty placeholder checks.

5. **HTTP-Level N+1 Polling Loop Elimination**:
    - *Issue*: Every 5 seconds, the frontend would fetch the URLs list and then launch parallel asynchronous network fetches for the check history of *every single URL* on the page. This created severe network congestion and server load ($N+1$ requests every 5 seconds).
    - *Correction*: Folded the check history retrieval directly into the backend `GET /urls` endpoint as a `recent_checks` list. Cleaned up all fetching loops and completely removed the redundant `checkHistories` state from the frontend, reducing network traffic to exactly 1 request per polling cycle.

6. **SQLite Cascade Deletion Enforcement**:
    - *Issue*: Deleted URLs left orphaned check records in the database, bloating storage. This occurred because `passive_deletes=True` was bypasssing SQLAlchemy's cascading deletes when SQLite foreign key constraints were bypassed or un-enforced by database clients.
    - *Correction*: Removed `passive_deletes=True` from the SQLAlchemy relationship, forcing SQLAlchemy to explicitly delete child check records in Python when a URL is deleted. Executed a clean-up script to wipe existing orphans.

7. **SQLite Connection-Level Foreign Key Enforcement**:
    - *Issue*: SQLite ignores `ON DELETE CASCADE` foreign key constraints by default unless the connection runs `PRAGMA foreign_keys=ON` on initialization. If another query or database client bypassed SQLAlchemy, the database itself would not enforce the constraint.
    - *Correction*: Added an `@event.listens_for(Engine, "connect")` listener in `database.py` to automatically execute `PRAGMA foreign_keys=ON` for every connection established by the SQLAlchemy engine, ensuring robust DB-level cascade deletes.

---
