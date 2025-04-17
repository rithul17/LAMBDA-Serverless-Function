import os
import time
import shutil
import tempfile
import docker
import signal

# Initialize docker client
client = docker.from_env()

# Global in-memory container pool
container_pool = {}
container_pool_gvisor = {}

def build_function_image(function_id: int, language: str, code: str) -> str:
    """
    Build a Docker image for the function based on its language and code.
    """
    build_dir = tempfile.mkdtemp(prefix=f"function_{function_id}_")
    
    try:
        if language.lower() == "python":
            code_filename = "function.py"
            tag = f"function_{function_id}_python:latest"
            dockerfile_content = (
                "FROM python:3.8-slim\n"
                "WORKDIR /app\n"
                "COPY function.py /app/function.py\n"
                "CMD [\"python\", \"function.py\"]\n"
            )
        elif language.lower() == "javascript":
            code_filename = "function.js"
            tag = f"function_{function_id}_javascript:latest"
            dockerfile_content = (
                "FROM node:14-slim\n"
                "WORKDIR /app\n"
                "COPY function.js /app/function.js\n"
                "CMD [\"node\", \"function.js\"]\n"
            )
        else:
            raise ValueError("Unsupported language. Only 'python' and 'javascript' are supported.")

        # Write the function code to the appropriate file.
        code_filepath = os.path.join(build_dir, code_filename)
        with open(code_filepath, "w") as code_file:
            code_file.write(code)

        # Write the Dockerfile.
        dockerfile_path = os.path.join(build_dir, "Dockerfile")
        with open(dockerfile_path, "w") as df:
            df.write(dockerfile_content)

        # Build the docker image.
        print(f"Building image '{tag}' for function {function_id}...")
        image, build_logs = client.images.build(path=build_dir, tag=tag)
        
        # Optionally, display build logs.
        for chunk in build_logs:
            if "stream" in chunk:
                print(chunk["stream"].strip())
                
        return tag
    finally:
        # Clean up temporary build directory.
        shutil.rmtree(build_dir)

def warm_start_container(function_id: int, image_tag: str):
    """
    Start a warm container for the given function.
    """
    try:
        print(f"[Pool] Warming up container for function {function_id} using image '{image_tag}'...")
        container = client.containers.run(image_tag, command="tail -f /dev/null", detach=True)
        return container
    except docker.errors.DockerException as de:
        print(f"[Pool] Error warming container: {str(de)}")
        raise de

def get_warm_container(function_id: int, image_tag: str):
    """
    Get an available warm container for the given function.
    """
    pool = container_pool.get(function_id, [])
    if pool:
        container = pool.pop(0)
        print(f"[Pool] Reusing warm container for function {function_id}.")
        return container
    else:
        return warm_start_container(function_id, image_tag)

def return_container_to_pool(function_id: int, container):
    """
    Return the container to the pool after use.
    """
    container_pool.setdefault(function_id, []).append(container)
    print(f"[Pool] Container returned to pool for function {function_id}.")

def update_container_code(container, code: str, language: str):
    """
    Update the code in the container with new code.
    """
    code_file = "function.py" if language.lower() == "python" else "function.js"
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
        tmp.write(code)
        tmp.flush()
        tmp_path = tmp.name
    
    try:
        # Copy the new code file into the container
        cmd = f"docker cp {tmp_path} {container.id}:/app/{code_file}"
        print(f"[Update] Running: {cmd}")
        result = os.system(cmd)
        if result != 0:
            print(f"[Update] Failed to update code in container: {result}")
            raise Exception(f"Failed to update code in container: {result}")
    finally:
        os.unlink(tmp_path)  # Remove temporary file

def run_function_in_pool(function_id: int, image_tag: str, language: str, timeout: int, code: str = None) -> dict:
    """
    Execute function in a Docker container, with the option to update the code.
    """
    container = get_warm_container(function_id, image_tag)
    
    # If code is provided, update it in the container
    if code is not None:
        try:
            update_container_code(container, code, language)
        except Exception as e:
            print(f"[Exec] Failed to update code: {str(e)}")
            try:
                container.remove(force=True)
            except:
                pass
            # Recreate container with fresh code
            container = warm_start_container(function_id, image_tag)
    
    start_time = time.time()
    
    try:
        if language.lower() == "python":
            cmd = "python function.py"
        elif language.lower() == "javascript":
            cmd = "node function.js"
        else:
            raise ValueError("Unsupported language.")
        
        print(f"[Exec] Executing command '{cmd}' in Docker container for function {function_id}.")
        exec_result = container.exec_run(cmd=cmd, demux=True)
        exit_code = exec_result.exit_code
        stdout, stderr = exec_result.output if exec_result.output else (b"", b"")
        execution_time = time.time() - start_time
        
        # Query container stats after execution
        stats = container.stats(stream=False)
        memory_usage = stats.get("memory_stats", {}).get("usage", 0)
        cpu_usage = stats.get("cpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0)
        
        logs = (stdout.decode("utf-8") if stdout else "") + (stderr.decode("utf-8") if stderr else "")
        result = {
            "logs": logs,
            "execution_time": execution_time,
            "exit_code": exit_code,
            "cpu_usage": cpu_usage,
            "memory_usage": memory_usage
        }
    except Exception as e:
        result = {"error": str(e)}
        try:
            container.kill()
            container.remove()
        except Exception:
            pass
        return result

    return_container_to_pool(function_id, container)
    return result

def warm_start_container_gvisor(function_id: int, image_tag: str):
    """
    Starts a warm container using gVisor.
    """
    try:
        print(f"[Pool] Warming up gVisor container for function {function_id} using image '{image_tag}'...")
        container = client.containers.run(
            image_tag,
            command="tail -f /dev/null",
            detach=True,
            runtime="runsc"  # Use gVisor's runtime
        )
        return container
    except docker.errors.DockerException as de:
        print(f"[Pool] gVisor error while warming container: {str(de)}")
        raise de

def get_warm_container_gvisor(function_id: int, image_tag: str):
    pool = container_pool_gvisor.get(function_id, [])
    if pool:
        container = pool.pop(0)
        print(f"[Pool] Reusing gVisor container for function {function_id}.")
        return container
    else:
        return warm_start_container_gvisor(function_id, image_tag)

def return_container_to_pool_gvisor(function_id: int, container):
    container_pool_gvisor.setdefault(function_id, []).append(container)
    print(f"[Pool] gVisor container returned to pool for function {function_id}.")

def run_function_in_gvisor(function_id: int, image_tag: str, language: str, timeout: int, code: str = None) -> dict:
    """
    Execute function in a gVisor container, with the option to update the code.
    """
    container = get_warm_container_gvisor(function_id, image_tag)
    
    # If code is provided, update it in the container
    if code is not None:
        try:
            update_container_code(container, code, language)
        except Exception as e:
            print(f"[Exec] Failed to update code in gVisor container: {str(e)}")
            try:
                container.remove(force=True)
            except:
                pass
            # Recreate container with fresh code
            container = warm_start_container_gvisor(function_id, image_tag)
    
    start_time = time.time()
    
    try:
        if language.lower() == "python":
            cmd = "python function.py"
        elif language.lower() == "javascript":
            cmd = "node function.js"
        else:
            raise ValueError("Unsupported language.")
        
        print(f"[Exec] Executing command '{cmd}' in gVisor container for function {function_id}.")
        exec_result = container.exec_run(cmd=cmd, demux=True)
        exit_code = exec_result.exit_code
        stdout, stderr = exec_result.output if exec_result.output else (b"", b"")
        execution_time = time.time() - start_time
        
        stats = container.stats(stream=False)
        memory_usage = stats.get("memory_stats", {}).get("usage", 0)
        cpu_usage = stats.get("cpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0)
        
        logs = (stdout.decode("utf-8") if stdout else "") + (stderr.decode("utf-8") if stderr else "")
        result = {
            "logs": logs,
            "execution_time": execution_time,
            "exit_code": exit_code,
            "cpu_usage": cpu_usage,
            "memory_usage": memory_usage
        }
    except Exception as e:
        result = {"error": str(e)}
        try:
            container.kill()
            container.remove()
        except Exception:
            pass
        return result

    return_container_to_pool_gvisor(function_id, container)
    return result
