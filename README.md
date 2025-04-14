time to get S grade in this boi

# Architecture Overview
Components

    Frontend (Monitoring Dashboard)

        Built with Streamlit or a similar framework.
        Allows users to deploy, manage, and monitor functions.
        Displays real-time metrics: request volume, response times, error rates, and resource utilization.

    Backend API Server

        Implemented using FastAPI (Python).
        Exposes RESTful endpoints for:
            Function deployment and management (CRUD operations).
            Triggering function executions via HTTP requests.
            Retrieving execution metrics and logs.

    Database

        Stores function metadata:
            Function name, route, language, timeout settings.
            Execution constraints and user information.
        Stores execution metrics and logs.

    Execution Engine

        Manages function execution environments.
        Supports multiple virtualization technologies:
            Docker Containers: For general-purpose function execution.
            Firecracker MicroVMs: For lightweight, secure, and fast-starting environments.
        Implements:
            Pre-warmed execution environments to reduce cold start latency.
            Request batching for efficient resource utilization.
            Timeout enforcement and resource usage restrictions.

    Metrics Collector

        Aggregates execution data:
            Response times, error rates, resource consumption.
        Provides data to the monitoring dashboard for visualization.

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

Task Scheduler:

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


```
serverless-platform/
├── backend/
│   ├── api/
│   │   ├── routes/
│   │   ├── controllers/
│   │   │   ├── functionsController.js
│   │   │   └── metricsController.js
│   │   ├── app.js
│   │   └── functions.js
│   ├── execution-engine/
│   │   ├── docker/
│   │   │   ├── python/
│   │   │   │   └── Dockerfile
│   │   │   └── javascript/
│   │   │       └── Dockerfile
│   │   ├── firecracker/
│   │   │   └── setup_scripts/
│   │   └── nanos/
│   │       └── setup_scripts/
│   ├── metrics/
│   │   ├── collector.js
│   │   └── aggregator.js
│   ├── database/
│   │   ├── models/
│   │   │   ├── function.js
│   │   │   └── metrics.js
│   │   └── index.js
│   └── utils/
│       ├── logger.js
│       └── config.js
├── frontend/
│   ├── components/
│   │   ├── FunctionForm.js
│   │   ├── FunctionList.js
│   │   └── MetricsDashboard.js
│   ├── pages/
│   │   ├── index.js
│   │   └── functionDetails.js
│   └── app.js
├── scripts/
│   ├── deploy.sh
│   └── setup_env.sh
├── tests/
│   ├── backend/
│   └── frontend/
├── docs/
│   ├── architecture.md
│   └── api_spec.md
├── .env
├── .gitignore
├── docker-compose.yml
├── package.json
└── README.md
```
