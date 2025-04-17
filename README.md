time to get S grade in this boi

# Serverless Function Execution Platform
---
## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Project Structure](#project-structure)
- [Setup & Installation](#setup--installation)
  - [Backend](#backend)
  - [Frontend](#frontend)
- [Docker & gVisor Runtime Configuration](#docker--gvisor-runtime-configuration)
- [Running the Backend](#running-the-backend)
- [Running the Frontend](#running-the-frontend)
- [API Endpoints](#api-endpoints)
  - [Function CRUD](#function-crud)
  - [Execute Function](#execute-function)
  - [Metrics](#metrics)
- [Usage Examples (curl)](#usage-examples-curl)
- [Notes & Next Steps](#notes--next-steps)

---

## Architecture Overview

1. **FastAPI Backend**: Manages function metadata, image building, container pooling, execution, and metrics storage (SQLite + SQLAlchemy).
2. **Docker Executor Module**: Builds Docker images for user functions, maintains a warm container pool, and runs code with timeout enforcement.
3. **gVisor Integration**: Optional execution mode using the `runsc` runtime for lightweight isolation.
4. **Streamlit Frontend**: Multi-page UI for managing functions (CRUD), invoking executions (Docker/gVisor), and visualizing metrics.

---

## Features

- **Function Management**: Create, read, update, delete functions via REST API or frontend.
- **On-Demand Execution**: Run user-provided code with Docker or gVisor environments.
- **Container Pooling**: Pre-warmed containers to reduce cold-start latency.
- **Dual Virtualization**: Compare performance between Docker and gVisor runtimes.
- **Real-Time Monitoring**: View per-function execution metrics and trends in the dashboard.

---

## Prerequisites

- **Operating System**: Arch Linux (or any Linux with Docker & gVisor support)
- **Docker**: Ensure Docker Engine is installed and running.
- **Python 3.10+**
- **runsc (gVisor)**: For gVisor mode (optional). Install via AUR or official instructions.

---

## Project Structure
>>>>>>> a01ac9e (final README)

```
project-root/
│
├── backend/
│   ├── main.py              # FastAPI application
│   ├── docker_executor.py   # Docker & gVisor execution logic
│   ├── functions.db         # SQLite database
│   └── requirements.txt     # Python dependencies for backend
│
├── frontend/
│   └── streamlit_app.py     
│   └── requirements.txt     # Python dependencies for frontend
│
└── README.md                
```

---

## Setup & Installation

### Backend

1. **Navigate to backend folder**:
   ```bash
   cd backend
   ```
2. **Create & activate a virtual environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

### Frontend

1. **Navigate to frontend folder** (or project root if it’s in the same directory):
   ```bash
   cd frontend
   ```
2. **Install Streamlit & dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

---

## Running the Backend

Within `backend/` venv:

```bash
uvicorn main:app --reload
```
or if you are special then use this command
to ensure that the python interpreter is used while running uvicorn

```bash
python -m uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.

---

## Running the Frontend

From the `frontend/` folder or project root:

```bash
streamlit run streamlit_app.py
```

Open the displayed URL (e.g., `http://localhost:8501`) in your browser.

---

## API Endpoints

### Function CRUD

| Method | Endpoint              | Description                      |
|--------|-----------------------|----------------------------------|
| POST   | `/functions/`         | Create a new function metadata   |
| GET    | `/functions/`         | List all functions               |
| GET    | `/functions/{id}`     | Get function by ID               |
| PUT    | `/functions/{id}`     | Update function metadata         |
| DELETE | `/functions/{id}`     | Delete a function                |

### Execute Function

```
POST /execute/{id}?mode=<docker|gvisor>
Body: { "code": "...user code..." }
```

Returns JSON with:
- `logs`: combined stdout/stderr from execution
- `execution_time`: time in seconds
- `exit_code` or `error`

### Metrics

| Method | Endpoint              | Description                           |
|--------|-----------------------|---------------------------------------|
| GET    | `/metrics/`           | Aggregate metrics for all functions   |

*Note: to get metrics per function, filter the `/metrics/` result by `function_id`.*

---

## Usage Examples (curl)

```bash
# Create a function
curl -X POST http://localhost:8000/functions/ \
     -H "Content-Type: application/json" \
     -d '{"name":"f1","route":"/exec/f1","language":"python","timeout":30}'

# Execute in Docker
curl -X POST "http://localhost:8000/execute/1?mode=docker" \
     -H "Content-Type: application/json" \
     -d '{"code":"print(\"Hello\")"}'

# Execute in gVisor
curl -X POST "http://localhost:8000/execute/1?mode=gvisor" \
     -H "Content-Type: application/json" \
     -d '{"code":"print(\"Hi gVisor\")"}'

# Fetch all metrics
curl http://localhost:8000/metrics/
```

---
