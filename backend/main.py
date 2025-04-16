from fastapi import FastAPI, HTTPException, Depends, Body
from pydantic import BaseModel, Field
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

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


# CRUD Endpoints from Task 2

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
# Enhanced /execute Endpoint (with Container Pool and Warm-up)
# ----------------------
@app.post("/execute/{function_id}")
def execute_function(function_id: int, execution: FunctionExecution, db: Session = Depends(get_db)):
    """
    This endpoint builds (or reuses) a Docker image for the function,
    warms up a container if none is available, and then executes the function code
    using a container from the pool. It returns logs, execution time, and error
    information if applicable.
    """
    # Lookup function metadata.
    db_function = db.query(Function).filter(Function.id == function_id).first()
    if db_function is None:
        raise HTTPException(status_code=404, detail="Function metadata not found.")

    try:
        # Build the Docker image (in a real system, you might cache images to avoid rebuilding).
        image_tag = docker_executor.build_function_image(function_id, db_function.language, execution.code)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error building Docker image: {str(e)}")
    
    # Run the function using a warm container from the pool.
    result = docker_executor.run_function_in_pool(function_id, image_tag, db_function.language, db_function.timeout)
    return result


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
