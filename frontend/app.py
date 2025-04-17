#app.py

import streamlit as st
import requests
import pandas as pd

API_URL = "http://localhost:8000"

st.set_page_config(page_title="Serverless Function Platform", layout="wide")

st.title("🐳 Serverless Function Platform")

# Navigation of Tabs
tabs = st.tabs(["Manage Functions", "Execute Function", "View Metrics"])

# 1. Manage Functions 
with tabs[0]:
    st.header("Manage Functions")
    with st.expander("Create New Function"):
        with st.form("create_fn"):
            name = st.text_input("Function Name", "")
            language = st.selectbox("Language", ["python", "javascript"])
            timeout = st.number_input("Timeout (s)", min_value=1, value=30)
            submitted = st.form_submit_button("Create")
            if submitted:
                payload = {
                    "name": name,
                    "route": f"/execute/{name}",
                    "language": language,
                    "timeout": timeout
                }
                r = requests.post(f"{API_URL}/functions/", json=payload)
                if r.ok:
                    st.success("Function created!")
                else:
                    st.error(f"Error: {r.text}")

    # List existing functions
    r = requests.get(f"{API_URL}/functions/")
    if r.ok:
        df = pd.DataFrame(r.json())
        if not df.empty:
            df_display = df[["id", "name", "language", "timeout", "route"]]
            st.dataframe(df_display, use_container_width=True)
            # Delete action
            with st.form("delete_fn"):
                fn_id = st.selectbox("Function to delete", df["id"])
                if st.form_submit_button("Delete"):
                    dr = requests.delete(f"{API_URL}/functions/{fn_id}")
                    if dr.ok:
                        st.success(f"Deleted function {fn_id}")
                    else:
                        st.error(f"Error: {dr.text}")
        else:
            st.info("No functions defined yet.")
    else:
        st.error("Failed to fetch functions.")

# 2. Execute Function 
with tabs[1]:
    st.header("Execute Function")
    # Fetch functions for dropdown
    r = requests.get(f"{API_URL}/functions/")
    if r.ok:
        fns = r.json()
        if fns:
            fn_map = {f"{f['id']} — {f['name']}": f["id"] for f in fns}
            sel = st.selectbox("Select Function", list(fn_map.keys()))
            fn_id = fn_map[sel]
            mode = st.radio("Execution Mode", ["docker", "gvisor"])
            code = st.text_area("Function Code", height=200)
            if st.button("Run"):
                payload = {"code": code}
                params = {"mode": mode}
                exec_resp = requests.post(
                    f"{API_URL}/execute/{fn_id}", json=payload, params=params
                )
                if exec_resp.ok:
                    res = exec_resp.json()
                    st.subheader("🔍 Execution Result")
                    st.text(f"Exit Code: {res.get('exit_code')}")
                    st.text(f"Time (s): {res.get('execution_time'):.4f}")
                    st.text(f"CPU Usage: {res.get('cpu_usage')}")
                    st.text(f"Memory Usage: {res.get('memory_usage')}")
                    st.subheader("📜 Logs")
                    st.code(res.get("logs", ""), language="bash")
                else:
                    st.error(f"Execution failed: {exec_resp.text}")
        else:
            st.info("No functions available to execute. Create one first!")
    else:
        st.error("Could not retrieve functions list.")

# 3. View Metrics 
with tabs[2]:
    st.header("Metrics Aggregation")
    m = requests.get(f"{API_URL}/metrics/")
    if m.ok:
        metrics = m.json()
        if metrics:
            dfm = pd.DataFrame(metrics)
            st.dataframe(dfm, use_container_width=True)
            # Simple charts
            st.line_chart(dfm.set_index("function_id")[["average_response_time", "average_cpu_usage", "average_memory_usage"]])
        else:
            st.info("No execution metrics recorded yet.")
    else:
        st.error("Failed to fetch metrics.")
