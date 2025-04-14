time to get S grade in this boi

# Architecture Overview
Components

    Frontend (Monitoring Dashboard)

        Built with Streamlit or a similar framework.
        Allows users to deploy, manage, and monitor functions.
        Displays real-time metrics: request volume, response times, error rates, and resource utilization.

    Backend API Server

        Implemented using Express (Node.js) or FastAPI (Python).
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
            Nanos Unikernels (optional): For specialized, minimal-footprint applications.
        Implements:
            Pre-warmed execution environments to reduce cold start latency.
            Request batching for efficient resource utilization.
            Timeout enforcement and resource usage restrictions.

    Metrics Collector

        Aggregates execution data:
            Response times, error rates, resource consumption.
        Provides data to the monitoring dashboard for visualization.


# intial project folder structure

serverless-platform/
├── backend/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── functions.js
│   │   │   └── metrics.js
│   │   ├── controllers/
│   │   │   ├── functionsController.js
│   │   │   └── metricsController.js
│   │   └── app.js
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

