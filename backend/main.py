from fastapi import FastAPI, HTTPException, Depends, Body, Query
from pydantic import BaseModel, Field
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer, String, DateTime, func, Float, case
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
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

# SQLAlchemy model for Execution Metrics (with resource metrics)
class ExecutionMetrics(Base):
    __tablename__ = "execution_metrics"
    id = Column(Integer, primary_key=True, index=True)
    function_id = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    response_time = Column(Float, nullable=False)  # in seconds (float for high precision)
    exit_code = Column(Integer, nullable=True)
    error = Column(String, nullable=True)
    cpu_usage = Column(Float, nullable=True)    # Raw CPU usage metric from container
    memory_usage = Column(Float, nullable=True) # Memory usage in bytes

# Create all tables in the database (if they don't exist)
Base.metadata.create_all(bind=engine)

# Pydantic schemas
class FunctionCreate(BaseModel):
    name: str = Field(..., example="my_function")
    route: str = Field(..., example="/execute/my_function")
    language: str = Field(..., example="python")
    timeout: int = Field(..., example=30)

class FunctionRead(FunctionCreate):
    id: int
    class Config:
        orm_mode = True

class FunctionExecution(BaseModel):
    code: str = Field(..., example="print('Hello, world!')")

class MetricsAggregate(BaseModel):
    function_id: int
    total_executions: int
    average_response_time: float
    average_cpu_usage: float
    average_memory_usage: float
    error_count: int

# Dependency to get DB session for each request
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# FastAPI app initialization
app = FastAPI(title="Serverless Function API with Docker & gVisor Execution and Metrics")

@app.get("/")
def read_root():
    return {"message": "Welcome to the Serverless Function API"}

# CRUD Endpoints for Function metadata
@app.post("/functions/", response_model=FunctionRead)
def create_function(function: FunctionCreate, db: Session = Depends(get_db)):
    db_function = Function(**function.dict())
    db.add(db_function)
    db.commit()
    db.refresh(db_function)
    return db_function

@app.get("/functions/", response_model=List[FunctionRead])
def read_functions(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    functions = db.query(Function).offset(skip).limit(limit).all()
    return functions

@app.get("/functions/{function_id}", response_model=FunctionRead)
def read_function(function_id: int, db: Session = Depends(get_db)):
    db_function = db.query(Function).filter(Function.id == function_id).first()
    if db_function is None:
        raise HTTPException(status_code=404, detail="Function not found")
    return db_function

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

@app.delete("/functions/{function_id}")
def delete_function(function_id: int, db: Session = Depends(get_db)):
    db_function = db.query(Function).filter(Function.id == function_id).first()
    if db_function is None:
        raise HTTPException(status_code=404, detail="Function not found")
    db.delete(db_function)
    db.commit()
    return {"detail": f"Function id {function_id} deleted."}

# Enhanced /execute Endpoint with Metrics Collection including resource metrics
@app.post("/execute/{function_id}")
def execute_function(
    function_id: int,
    execution: FunctionExecution,
    mode: str = Query("docker", description="Execution mode: 'docker' (default) or 'gvisor'"),
    db: Session = Depends(get_db)
):
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
    
    response_time = float(result.get("execution_time", 0))
    exit_code = result.get("exit_code")
    error_msg = result.get("error")
    cpu_usage = float(result.get("cpu_usage", 0))
    memory_usage = float(result.get("memory_usage", 0))
    
    metrics_record = ExecutionMetrics(
        function_id=function_id,
        response_time=response_time,
        exit_code=exit_code,
        error=error_msg,
        cpu_usage=cpu_usage,
        memory_usage=memory_usage
    )
    db.add(metrics_record)
    db.commit()
    
    return result

# Metrics Aggregation Endpoint with resource metrics
@app.get("/metrics/", response_model=List[MetricsAggregate])
def aggregate_metrics(db: Session = Depends(get_db)):
    aggregates = (
        db.query(
            ExecutionMetrics.function_id,
            func.count(ExecutionMetrics.id).label("total_executions"),
            func.avg(ExecutionMetrics.response_time).label("average_response_time"),
            func.avg(ExecutionMetrics.cpu_usage).label("average_cpu_usage"),
            func.avg(ExecutionMetrics.memory_usage).label("average_memory_usage"),
            func.sum(case((ExecutionMetrics.error != None, 1), else_=0)).label("error_count")
        )
        .group_by(ExecutionMetrics.function_id)
        .all()
    )
    
    result = [
        MetricsAggregate(
            function_id=agg.function_id,
            total_executions=agg.total_executions,
            average_response_time=float(agg.average_response_time or 0),
            average_cpu_usage=float(agg.average_cpu_usage or 0),
            average_memory_usage=float(agg.average_memory_usage or 0),
            error_count=agg.error_count or 0
        )
        for agg in aggregates
    ]
    return result

