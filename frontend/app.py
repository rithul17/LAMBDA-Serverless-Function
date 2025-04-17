import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import json
from datetime import datetime

# API Base URL - Change this to match your FastAPI deployment
API_BASE_URL = "http://localhost:8000"

# Set page config
st.set_page_config(
    page_title="Serverless Function Platform",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Navigation sidebar
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Home", "Manage Functions", "Execute Function", "Metrics"])

def home_page():
    st.title("Serverless Function Platform")
    st.markdown("""
    ### Welcome to the Serverless Function Platform!
    
    This platform allows you to create, manage, and execute serverless functions in isolated Docker containers
    with optional gVisor security, and view performance metrics.
    
    #### Features:
    
    - **Create and manage functions** with support for Python and JavaScript
    - **Execute functions** in either Docker containers or gVisor for enhanced security
    - **Monitor performance metrics** including execution time, CPU and memory usage
    - **Container pooling** for improved cold start performance
    
    Use the navigation panel on the left to get started!
    """)
    
    # Show a sample of the latest functions
    try:
        functions = requests.get(f"{API_BASE_URL}/functions/").json()
        
        if functions:
            st.subheader("Recent Functions")
            df = pd.DataFrame(functions)
            st.dataframe(df)
        else:
            st.info("No functions created yet. Head to the 'Manage Functions' page to create one!")
    except Exception as e:
        st.error(f"Error connecting to the backend: {e}")

def manage_functions_page():
    st.title("Manage Functions")
    
    # Create tabs for CRUD operations
    tab1, tab2, tab3, tab4 = st.tabs(["Create", "View/List", "Update", "Delete"])
    
    with tab1:
        st.header("Create Function")
        with st.form("create_function_form"):
            name = st.text_input("Function Name")
            route = st.text_input("Route", placeholder="/execute/my_function")
            language = st.selectbox("Language", ["python", "javascript"])
            timeout = st.number_input("Timeout (seconds)", min_value=1, value=30)
            
            submitted = st.form_submit_button("Create Function")
            if submitted:
                if not name or not route:
                    st.error("Name and Route are required fields.")
                else:
                    try:
                        data = {
                            "name": name,
                            "route": route,
                            "language": language,
                            "timeout": timeout
                        }
                        response = requests.post(f"{API_BASE_URL}/functions/", json=data)
                        if response.status_code == 200:
                            st.success(f"Function '{name}' created successfully!")
                            st.json(response.json())
                        else:
                            st.error(f"Error creating function: {response.text}")
                    except Exception as e:
                        st.error(f"Error connecting to backend: {e}")
    
    with tab2:
        st.header("View Functions")
        try:
            response = requests.get(f"{API_BASE_URL}/functions/")
            if response.status_code == 200:
                functions = response.json()
                if functions:
                    df = pd.DataFrame(functions)
                    st.dataframe(df)
                    
                    # Show details of a selected function
                    selected_function_id = st.selectbox(
                        "Select a function to view details", 
                        options=[f["id"] for f in functions],
                        format_func=lambda x: next((f["name"] for f in functions if f["id"] == x), str(x))
                    )
                    
                    if selected_function_id:
                        selected_function = next((f for f in functions if f["id"] == selected_function_id), None)
                        if selected_function:
                            st.subheader(f"Function Details: {selected_function['name']}")
                            st.json(selected_function)
                else:
                    st.info("No functions found. Create one in the 'Create' tab.")
            else:
                st.error(f"Error fetching functions: {response.text}")
        except Exception as e:
            st.error(f"Error connecting to backend: {e}")
    
    with tab3:
        st.header("Update Function")
        try:
            response = requests.get(f"{API_BASE_URL}/functions/")
            if response.status_code == 200:
                functions = response.json()
                if functions:
                    selected_function_id = st.selectbox(
                        "Select a function to update", 
                        options=[f["id"] for f in functions],
                        format_func=lambda x: next((f["name"] for f in functions if f["id"] == x), str(x)),
                        key="update_function_select"
                    )
                    
                    if selected_function_id:
                        selected_function = next((f for f in functions if f["id"] == selected_function_id), None)
                        
                        with st.form("update_function_form"):
                            name = st.text_input("Function Name", value=selected_function["name"])
                            route = st.text_input("Route", value=selected_function["route"])
                            language = st.selectbox("Language", ["python", "javascript"], index=0 if selected_function["language"] == "python" else 1)
                            timeout = st.number_input("Timeout (seconds)", min_value=1, value=selected_function["timeout"])
                            
                            submitted = st.form_submit_button("Update Function")
                            if submitted:
                                if not name or not route:
                                    st.error("Name and Route are required fields.")
                                else:
                                    try:
                                        data = {
                                            "name": name,
                                            "route": route,
                                            "language": language,
                                            "timeout": timeout
                                        }
                                        response = requests.put(f"{API_BASE_URL}/functions/{selected_function_id}", json=data)
                                        if response.status_code == 200:
                                            st.success(f"Function '{name}' updated successfully!")
                                            st.json(response.json())
                                        else:
                                            st.error(f"Error updating function: {response.text}")
                                    except Exception as e:
                                        st.error(f"Error connecting to backend: {e}")
                else:
                    st.info("No functions found. Create one in the 'Create' tab.")
            else:
                st.error(f"Error fetching functions: {response.text}")
        except Exception as e:
            st.error(f"Error connecting to backend: {e}")
    
    with tab4:
        st.header("Delete Function")
        try:
            response = requests.get(f"{API_BASE_URL}/functions/")
            if response.status_code == 200:
                functions = response.json()
                if functions:
                    selected_function_id = st.selectbox(
                        "Select a function to delete", 
                        options=[f["id"] for f in functions],
                        format_func=lambda x: next((f"{f['name']} (ID: {f['id']})" for f in functions if f["id"] == x), str(x)),
                        key="delete_function_select"
                    )
                    
                    if selected_function_id:
                        selected_function = next((f for f in functions if f["id"] == selected_function_id), None)
                        st.write(f"You are about to delete: **{selected_function['name']}**")
                        
                        if st.button("Delete Function", key="delete_button"):
                            try:
                                response = requests.delete(f"{API_BASE_URL}/functions/{selected_function_id}")
                                if response.status_code == 200:
                                    st.success(f"Function deleted successfully!")
                                    st.rerun()
                                else:
                                    st.error(f"Error deleting function: {response.text}")
                            except Exception as e:
                                st.error(f"Error connecting to backend: {e}")
                else:
                    st.info("No functions found. Create one in the 'Create' tab.")
            else:
                st.error(f"Error fetching functions: {response.text}")
        except Exception as e:
            st.error(f"Error connecting to backend: {e}")

def execute_function_page():
    st.title("Execute Function")
    
    try:
        response = requests.get(f"{API_BASE_URL}/functions/")
        if response.status_code == 200:
            functions = response.json()
            if functions:
                col1, col2 = st.columns(2)
                
                with col1:
                    selected_function_id = st.selectbox(
                        "Select a function to execute", 
                        options=[f["id"] for f in functions],
                        format_func=lambda x: next((f"{f['name']} ({f['language']})" for f in functions if f["id"] == x), str(x))
                    )
                
                with col2:
                    execution_mode = st.radio("Execution Mode", ["docker", "gvisor"], help="Docker is faster, gVisor provides better security isolation")
                
                if selected_function_id:
                    selected_function = next((f for f in functions if f["id"] == selected_function_id), None)
                    
                    language = selected_function["language"]
                    
                    # Default code examples based on language
                    default_code = ""
                    if language == "python":
                        default_code = """# Python function example
import time
import random

# Simulate some work
time.sleep(0.5)

# Generate some sample data
data = [random.randint(1, 100) for _ in range(10)]
total = sum(data)
average = total / len(data)

print(f"Data: {data}")
print(f"Sum: {total}")
print(f"Average: {average}")

# Return some resource info
import os
import psutil
process = psutil.Process(os.getpid())
print(f"Memory usage: {process.memory_info().rss / 1024 / 1024:.2f} MB")
"""
                    elif language == "javascript":
                        default_code = """// JavaScript function example
const start = Date.now();

// Simulate some work
setTimeout(() => {
  // Generate some sample data
  const data = Array.from({length: 10}, () => Math.floor(Math.random() * 100));
  const total = data.reduce((a, b) => a + b, 0);
  const average = total / data.length;

  console.log(`Data: ${JSON.stringify(data)}`);
  console.log(`Sum: ${total}`);
  console.log(`Average: ${average}`);
  
  // Execution time
  console.log(`Execution time: ${Date.now() - start}ms`);
  
  // Exit the timeout
}, 500);
"""
                    
                    code = st.text_area("Function Code", height=300, value=default_code)
                    
                    if st.button("Execute Function"):
                        with st.spinner("Executing function..."):
                            try:
                                data = {"code": code}
                                response = requests.post(
                                    f"{API_BASE_URL}/execute/{selected_function_id}?mode={execution_mode}", 
                                    json=data
                                )
                                
                                if response.status_code == 200:
                                    result = response.json()
                                    
                                    st.success("Function executed successfully!")
                                    
                                    # Display execution results in tabs
                                    output_tab, metrics_tab = st.tabs(["Output", "Execution Metrics"])
                                    
                                    with output_tab:
                                        st.subheader("Function Output")
                                        logs = result.get("logs", "")
                                        if logs:
                                            st.text_area("Logs", value=logs, height=200, disabled=True)
                                        else:
                                            st.info("No output from function.")
                                    
                                    with metrics_tab:
                                        st.subheader("Execution Metrics")
                                        col1, col2, col3 = st.columns(3)
                                        
                                        with col1:
                                            st.metric("Execution Time", f"{result.get('execution_time', 0):.4f} sec")
                                        
                                        with col2:
                                            cpu = result.get('cpu_usage', 0)
                                            # Format CPU usage to be more readable
                                            if cpu > 1_000_000_000:
                                                cpu_display = f"{cpu / 1_000_000_000:.2f} Gcycles"
                                            else:
                                                cpu_display = f"{cpu / 1_000_000:.2f} Mcycles"
                                            st.metric("CPU Usage", cpu_display)
                                        
                                        with col3:
                                            memory = result.get('memory_usage', 0)
                                            # Format memory to be more readable
                                            if memory > 1_000_000:
                                                memory_display = f"{memory / 1_000_000:.2f} MB"
                                            else:
                                                memory_display = f"{memory / 1_000:.2f} KB"
                                            st.metric("Memory Usage", memory_display)
                                        
                                        st.metric("Exit Code", result.get('exit_code', 'N/A'))
                                        
                                        if "error" in result:
                                            st.error(f"Error during execution: {result['error']}")
                                else:
                                    st.error(f"Error executing function: {response.text}")
                            except Exception as e:
                                st.error(f"Error connecting to backend: {e}")
            else:
                st.info("No functions found. Create one in the 'Manage Functions' page.")
        else:
            st.error(f"Error fetching functions: {response.text}")
    except Exception as e:
        st.error(f"Error connecting to backend: {e}")

def metrics_page():
    st.title("Function Metrics")
    
    try:
        # Get metrics data
        metrics_response = requests.get(f"{API_BASE_URL}/metrics/")
        functions_response = requests.get(f"{API_BASE_URL}/functions/")
        
        if metrics_response.status_code == 200 and functions_response.status_code == 200:
            metrics = metrics_response.json()
            functions = functions_response.json()
            
            # Create a lookup dictionary for function names
            function_names = {f["id"]: f["name"] for f in functions}
            
            if metrics:
                # Add function names to metrics data
                for metric in metrics:
                    metric["function_name"] = function_names.get(metric["function_id"], f"Unknown (ID: {metric['function_id']})")
                
                # Convert to DataFrame for easier manipulation
                df = pd.DataFrame(metrics)
                
                st.subheader("Overall Function Metrics")
                st.dataframe(df)
                
                # Create visualizations
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Total Executions")
                    fig = px.bar(
                        df, 
                        x="function_name", 
                        y="total_executions",
                        color="function_name",
                        labels={"function_name": "Function", "total_executions": "Total Executions"}
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    st.subheader("Error Rate")
                    df["error_rate"] = (df["error_count"] / df["total_executions"] * 100).round(2)
                    fig = px.bar(
                        df, 
                        x="function_name", 
                        y="error_rate",
                        color="function_name",
                        labels={"function_name": "Function", "error_rate": "Error Rate (%)"}
                    )
                    fig.update_layout(yaxis_range=[0, 100])
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    st.subheader("Average Response Time")
                    fig = px.bar(
                        df, 
                        x="function_name", 
                        y="average_response_time",
                        color="function_name",
                        labels={"function_name": "Function", "average_response_time": "Avg Response Time (s)"}
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    st.subheader("Average Memory Usage")
                    # Convert to MB for readability
                    df["memory_mb"] = (df["average_memory_usage"] / 1_000_000).round(2)
                    fig = px.bar(
                        df, 
                        x="function_name", 
                        y="memory_mb",
                        color="function_name",
                        labels={"function_name": "Function", "memory_mb": "Avg Memory Usage (MB)"}
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                # Resource comparison
                st.subheader("Resource Comparison")
                fig = px.scatter(
                    df,
                    x="average_response_time",
                    y="memory_mb",
                    size="total_executions", 
                    color="function_name",
                    hover_name="function_name",
                    size_max=50,
                    labels={
                        "average_response_time": "Avg Response Time (s)",
                        "memory_mb": "Avg Memory Usage (MB)",
                        "function_name": "Function"
                    }
                )
                st.plotly_chart(fig, use_container_width=True)
                
            else:
                st.info("No metrics data available yet. Execute some functions to generate metrics.")
        else:
            st.error("Failed to fetch metrics or functions data.")
    except Exception as e:
        st.error(f"Error connecting to backend: {e}")

# Display the selected page
if page == "Home":
    home_page()
elif page == "Manage Functions":
    manage_functions_page()
elif page == "Execute Function":
    execute_function_page()
elif page == "Metrics":
    metrics_page()
