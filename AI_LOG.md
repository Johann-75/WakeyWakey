# AI Collaboration Log

This log records how the developer and the AI coding assistant (**Antigravity**) worked together to build **WakeyWakey**, a tool that monitors if websites are up or down.

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

### ☁️ Phase 6: Migration to Render & SQLite
* **Action**: Shifted deployment stack to Render + SQLite to support 100% free hosting. Purged redundant `/checks` history endpoint to reduce API footprint, simplified database connections to SQLite-only, and optimized build steps in the backend Dockerfile.
---

## 🔄 The Course Corrections

During development, several adjustments and optimizations were made to fix bugs and improve performance:

1. **Connecting Backend inside Docker**:
   - *Issue*: Initially, the backend was set to run on `127.0.0.1` (localhost). But when put inside a Docker container, this locked the backend inside its own container walls, preventing the frontend browser from reaching it.
   - *Correction*: Updated the backend Dockerfile to run on `0.0.0.0`, which opens the port so the frontend can successfully communicate with it.

2. **Configuring the Backend Address for the Frontend**:
   - *Issue*: Hardcoding the backend address (like `127.0.0.1:8000`) breaks the app when deploying it to different environments (like Railway or local Docker).
   - *Correction*: Set up a build setting (`ARG VITE_API_BASE_URL`) so that we can easily configure the backend address during deployment without editing the source code.

3. **Adding a Delete Button to the Dashboard**:
   - *Issue*: The backend server supported deleting websites, but the frontend dashboard had no button to do so.
   - *Correction*: Added a red delete cross (`✕`) next to each website on the dashboard table that lights up when you hover over it.

4. **Visualizing History with Status Dots**:
   - *Issue*: The old dashboard used a boring progress bar to show success rates, which made it hard to tell *when* a site went offline or if it had recovered.
   - *Correction*: Replaced it with a timeline of 5 status dots (oldest on the left, newest on the right) that glow green for success, red for downtime, and gray for empty slots where checks haven't run yet.

5. **Reducing Network Traffic (HTTP N+1 Fix)**:
   - *Issue*: Every 5 seconds, the dashboard fetched the list of websites and then launched *separate internet requests for every single website* to get its history. If you had 20 websites, this triggered 21 network calls every 5 seconds, clogging up browser traffic.
   - *Correction*: We merged the website details and their check history together inside the backend. Now, the dashboard makes exactly **one clean request** every 5 seconds to load everything.

6. **Cleaning Up Leftover History on Delete (Cascade Delete)**:
   - *Issue*: When you deleted a website, its ping history was left floating inside the database. Over time, this bloats the database size with useless junk records.
   - *Correction*: Set up a rule so that when a website is deleted, the database automatically deletes its associated ping history at the same time.

7. **Fixing SQLite Settings Intercepting PostgreSQL**:
   - *Issue*: We set up SQLite settings (like enabling foreign keys) globally. When the app ran in production with a PostgreSQL database, the app tried to apply these SQLite settings to PostgreSQL. This crashed PostgreSQL transactions and blocked all queries.
   - *Correction*: Restricted SQLite-only configuration settings to execute *only* when the database is SQLite, preventing any interference in production.

8. **Speeding up Database Loading (Database N+1 Query Fix)**:
   - *Issue*: Every time the website loaded, the server did one database check to get the list of websites, and then separate database checks for every single website to get its history. If you had 50 websites, this meant 51 database queries every 5 seconds, which made the app laggy.
   - *Correction*: We changed the code so that the server pulls all websites and all their recent history at the same time in just **two total queries**, making the page load much faster.

9. **Instant Website Addition**:
   - *Issue*: When you added a slow or offline website, the "Add URL" button would freeze on "Adding..." for up to 10 seconds because the server was trying to check the website before telling the browser it was saved.
   - *Correction*: We made the server save the website immediately (taking less than a second) and check the website's status in the background. The dashboard now shows it as `UNKNOWN` briefly, then updates to its true status on the next refresh.

10. **Fixing Auto-Formatting for Domains (like google.com)**:
    - *Issue*: If you typed `google.com` (without `https://`), the browser's built-in validator blocked the form submission and showed an error, preventing our code from automatically adding the `https://` prefix.
    - *Correction*: Added the `noValidate` setting to the HTML form. This tells the browser to skip its strict, native validation check so our JavaScript can successfully add the missing `https://` prefix for you.

11. **Saving System Resources**:
    - *Issue*: The background checker was spinning up extra system threads (which uses up more RAM and CPU) to run checking intervals.
    - *Correction*: Swapped the scheduler to run directly on the main application loop, which does the exact same job but wastes much less server memory.

12. **Setting Ping Speed Limits (Concurrency Cap)**:
    - *Issue*: If you monitored hundreds of websites, the server would try to ping all of them at the exact same millisecond, which could overload the server's network or trigger rate-limit blocks from target domains.
    - *Correction*: Added a rule (semaphore) to limit pings to a maximum of 20 at a time, checking websites in clean, controlled batches.

13. **Fixing False Latency Spikes (Stopwatch Timer Bug)**:
    - *Issue*: The server recorded the start time of a check before it waited in line for its turn in the concurrency queue. If many websites were queued, the delay spent waiting was added to the latency, making the website look slow even if it responded quickly.
    - *Correction*: Moved the stopwatch start inside the queue lock, ensuring we only measure the actual HTTP response latency.

14. **Unifying Database Path Resolution**:
    - *Issue*: Running the app locally without Docker created database files in different folders depending on whether you ran commands from the project root or the backend folder directly.
    - *Correction*: Configured smart folder detection so that SQLite resolves consistently to `backend/data/monitor.db` in both cases, preventing duplicate databases.

15. **Removing Unused API Endpoints**:
    - *Issue*: The backend had a separate `/urls/{url_id}/checks` history endpoint. However, the frontend dashboard was optimized to load all recent checks inline via the main `/urls` list endpoint, leaving the history endpoint unused.
    - *Correction*: Deleted the redundant endpoint to keep the API surface clean.

---
