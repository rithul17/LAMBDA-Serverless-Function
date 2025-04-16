from fastapi import FastAPI, HTTPException, Depends, Body, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from sqlalchemy import create_engine, Column, Integer, String, DateTime, func, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import case
from datetime import datetime
import docker_executor  # Import our docker_executor module

# ----------------------
# Database Configuration
# ----------------------
SQLALCHEMY_DATABASE_URL = "sqlite:///./functions.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# SQLAlchemy model for Function metadata
class Function(Base):
    __tablename__ = "functions"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    route = Column(String, index=True, unique=True, nullable=False)
    language = Column(String, nullable=False)
    timeout = Column(Integer, nullable=False)

class ExecutionMetrics(Base):
    __tablename__ = "execution_metrics"
    id = Column(Integer, primary_key=True, index=True)
    function_id = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    response_time = Column(Float, nullable=False)  # in seconds (or as float if needed)
    exit_code = Column(Integer, nullable=True)
    error = Column(String, nullable=True)

# Create all tables in the database (if they don't exist)
Base.metadata.create_all(bind=engine)

# Pydantic schema for input validation and response modeling
class FunctionCreate(BaseModel):
    name: str = Field(..., example="my_function")
    route: str = Field(..., example="/execute/my_function")
    language: str = Field(..., example="python")
    timeout: int = Field(..., example=30)

class FunctionRead(FunctionCreate):
    id: int

    class Config:
        orm_mode = True

# For execution requests, include the function code.
class FunctionExecution(BaseModel):
    code: str = Field(..., example="print('Hello, world!')")

class MetricsAggregate(BaseModel):
    function_id: int
    total_executions: int
    average_response_time: float
    error_count: int

# Dependency to get DB session for each request
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# FastAPI app initialization
app = FastAPI(title="Serverless Function API with Docker Execution")

# CRUD Endpoints
@app.get("/")
def read_root():
    return {"message": "Welcome to the Serverless Function API"}

# Create Function metadata
@app.post("/functions/", response_model=FunctionRead)
def create_function(function: FunctionCreate, db: Session = Depends(get_db)):
    db_function = Function(**function.dict())
    db.add(db_function)
    db.commit()
    db.refresh(db_function)
    return db_function

# Get all Functions
@app.get("/functions/", response_model=List[FunctionRead])
def read_functions(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    functions = db.query(Function).offset(skip).limit(limit).all()
    return functions

# Get specific Function by ID
@app.get("/functions/{function_id}", response_model=FunctionRead)
def read_function(function_id: int, db: Session = Depends(get_db)):
    db_function = db.query(Function).filter(Function.id == function_id).first()
    if db_function is None:
        raise HTTPException(status_code=404, detail="Function not found")
    return db_function

# Update Function by ID
@app.put("/functions/{function_id}", response_model=FunctionRead)
def update_function(function_id: int, function_update: FunctionCreate, db: Session = Depends(get_db)):
    db_function = db.query(Function).filter(Function.id == function_id).first()
    if db_function is None:
        raise HTTPException(status_code=404, detail="Function not found")
    for key, value in function_update.dict().items():
        setattr(db_function, key, value)
    db.commit()
    db.refresh(db_function)
    return db_function

# Delete Function by ID
@app.delete("/functions/{function_id}")
def delete_function(function_id: int, db: Session = Depends(get_db)):
    db_function = db.query(Function).filter(Function.id == function_id).first()
    if db_function is None:
        raise HTTPException(status_code=404, detail="Function not found")
    db.delete(db_function)
    db.commit()
    return {"detail": f"Function id {function_id} deleted."}


# ----------------------
# Enhanced /execute Endpoint with Metrics Collection
# ----------------------
@app.post("/execute/{function_id}")
def execute_function(
    function_id: int,
    execution: FunctionExecution,
    mode: str = Query("docker", description="Execution mode: 'docker' (default) or 'gvisor'"),
    db: Session = Depends(get_db)
):
    """
    Builds (or reuses) a Docker image for the function and then executes
    the function code using either the standard Docker container pool or
    gVisor containers (if mode=gvisor). Collects and stores execution metrics.
    """
    db_function = db.query(Function).filter(Function.id == function_id).first()
    if db_function is None:
        raise HTTPException(status_code=404, detail="Function metadata not found.")

    try:
        image_tag = docker_executor.build_function_image(function_id, db_function.language, execution.code)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error building Docker image: {str(e)}")
    
    if mode.lower() == "gvisor":
        result = docker_executor.run_function_in_gvisor(function_id, image_tag, db_function.language, db_function.timeout)
    else:
        result = docker_executor.run_function_in_pool(function_id, image_tag, db_function.language, db_function.timeout)
    
    # Collect metrics
    response_time = int(result.get("execution_time", 0))
    exit_code = result.get("exit_code")
    error_msg = result.get("error")
    
    metrics_record = ExecutionMetrics(
        function_id=function_id,
        response_time=response_time,
        exit_code=exit_code,
        error=error_msg
    )
    db.add(metrics_record)
    db.commit()
    
    return result

# ----------------------
# Metrics Aggregation Endpoint
# ----------------------

@app.get("/metrics/", response_model=List[MetricsAggregate])
def aggregate_metrics(db: Session = Depends(get_db)):
    """
    Aggregates execution metrics for each function.
    Returns total executions, average response time, and error count.
    """
    aggregates = (
        db.query(
            ExecutionMetrics.function_id,
            func.count(ExecutionMetrics.id).label("total_executions"),
            func.avg(ExecutionMetrics.response_time).label("average_response_time"),
            func.sum(case((ExecutionMetrics.error != None, 1), else_=0)).label("error_count")
        )
        .group_by(ExecutionMetrics.function_id)
        .all()
    )
    
    result: List[MetricsAggregate] = [
        MetricsAggregate(
            function_id=agg.function_id,
            total_executions=agg.total_executions,
            average_response_time=float(agg.average_response_time or 0),
            error_count=agg.error_count or 0
        )
        for agg in aggregates
    ]
    return result


## execution using 2 virt techs
#@app.post("/execute/{function_id}")
#def execute_function(
#    function_id: int,
#    execution: FunctionExecution,
#    mode: str = Query("docker", description="Execution mode: 'docker' (default) or 'gvisor'"),
#    db: Session = Depends(get_db)
#):
#    """
#    This endpoint builds (or reuses) a Docker image for the function,
#    and then executes the function code using either the standard Docker container pool or
#    gVisor containers (if mode=gvisor) for virtualization.
#    """
#    db_function = db.query(Function).filter(Function.id == function_id).first()
#    if db_function is None:
#        raise HTTPException(status_code=404, detail="Function metadata not found.")
#
#    try:
#        image_tag = docker_executor.build_function_image(function_id, db_function.language, execution.code)
#    except Exception as e:
#        raise HTTPException(status_code=500, detail=f"Error building Docker image: {str(e)}")
#    
#    if mode.lower() == "gvisor":
#        result = docker_executor.run_function_in_gvisor(function_id, image_tag, db_function.language, db_function.timeout)
#    else:
#        result = docker_executor.run_function_in_pool(function_id, image_tag, db_function.language, db_function.timeout)
#        
#    return result
#
#
## ----------------------
## Enhanced /execute Endpoint (with Container Pool and Warm-up)
## ----------------------
#@app.post("/execute/{function_id}")
#def execute_function(function_id: int, execution: FunctionExecution, db: Session = Depends(get_db)):
#    """
#    This endpoint builds (or reuses) a Docker image for the function,
#    warms up a container if none is available, and then executes the function code
#    using a container from the pool. It returns logs, execution time, and error
#    information if applicable.
#    """
#    # Lookup function metadata.
#    db_function = db.query(Function).filter(Function.id == function_id).first()
#    if db_function is None:
#        raise HTTPException(status_code=404, detail="Function metadata not found.")
#
#    try:
#        # Build the Docker image (in a real system, you might cache images to avoid rebuilding).
#        image_tag = docker_executor.build_function_image(function_id, db_function.language, execution.code)
#    except Exception as e:
#        raise HTTPException(status_code=500, detail=f"Error building Docker image: {str(e)}")
#    
#    # Run the function using a warm container from the pool.
#    result = docker_executor.run_function_in_pool(function_id, image_tag, db_function.language, db_function.timeout)
#    return result
#

 ## ----------------------
 ## Endpoint for Function Execution using Docker
 ## ----------------------
 #@app.post("/execute/{function_id}")
 #def execute_function(function_id: int, execution: FunctionExecution, db: Session = Depends(get_db)):
 #    """
 #    Endpoint to build a Docker image for the function and execute it with timeout enforcement.
 #    The function code is provided in the request body.
 #    """
 #    db_function = db.query(Function).filter(Function.id == function_id).first()
 #    if db_function is None:
 #        raise HTTPException(status_code=404, detail="Function metadata not found.")
 #
 #    try:
 #        # Build the docker image from the provided code.
 #        image_tag = build_function_image(function_id, db_function.language, execution.code)
 #    except Exception as e:
 #        raise HTTPException(status_code=500, detail=f"Error building Docker image: {str(e)}")
 #    
 #    # Run the container with the configured timeout
 #    result = run_function_image(image_tag, db_function.timeout)
 #    return result
 #
