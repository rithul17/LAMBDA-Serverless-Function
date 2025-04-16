time to get S grade in this boi

# High-Level Architecture:

    Frontend (Streamlit): 
    User Interface for function management (CRUD) and viewing the monitoring dashboard.

    Backend API (FastAPI):
        Handles HTTP requests from the Frontend (for management) and external clients (for function invocation).
        Manages function metadata in the SQLite database.
        Interacts with the Execution Engine.
        Serves aggregated metrics data to the Frontend dashboard.

    Execution Engine (Python Module within Backend):
        Receives invocation requests from the API.
        Manages a pool of pre-warmed containers (Docker & gVisor).
        Interacts with the Docker daemon (via Docker SDK or CLI) to run functions in containers/sandboxes.
        Enforces timeouts.
        Collects basic execution metrics (time, status, resource usage if easy).
        Stores metrics in the SQLite database.

    Virtualization Layer (Docker Engine):
        Runs standard Docker containers.
        Runs firecracker (preferred) or else gvisor sandboxes using runc runtime configured in docker

    Database (SQLite):
        Stores function metadata (name, route, language, timeout, code path, virtualization choice).
        Stores raw execution metrics (timestamp, duration, status, function_id, virtualization_tech).

# Business Logic
Frontend:

    Role: Provides a user interface for inputting function code and metadata.
    Action: Sends HTTP requests to the backend to deploy, update, or manage functions.

Backend:

    Role: Acts as the API gateway and business logic layer.
    Action:
        Listens for HTTP requests from the frontend.
        Receives function code and its accompanying metadata (e.g., function name, language, timeout settings, resource limits).
        Persists both the function code and its metadata in a database.

Wrapper:

    Role: Coordinates function execution.
    Action:
        Monitors the database (or a message queue) for functions that need to be executed.
        Retrieves the necessary function details from storage and assigns the execution task to the execution engine.

Execution Engine:

    Role: Executes the functions in an isolated environment.
    Action:
        Retrieves functions (code and metadata) handed off by the scheduler.
        Runs the functions using the appropriate virtualization technology (e.g., Docker, Firecracker microVMs, or similar).
        Enforces execution constraints (timeouts, resource limits) during function execution.

Metrics Collector:

    Role: Gathers performance and execution data from the execution engines.
    Action:
        Collects information such as response times, error rates, and resource utilization from the execution environments.
        Stores this aggregated data in a metrics store.
        Provides a dedicated REST endpoint that the frontend can query to display real-time monitoring dashboards.


