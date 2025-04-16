import os
import time
import shutil
import tempfile
import docker
import signal

# Initialize docker client (make sure Docker is running and you have the python docker package installed)
client = docker.from_env()

# Global in-memory container pool.
# Mapping function_id (int) -> list of warm containers
container_pool = {}

# gVisor pool (using runtime "runsc")
container_pool_gvisor = {}

def build_function_image(function_id: int, language: str, code: str) -> str:
    """
    Build a Docker image for the function based on its language and code.
    The function image tag is constructed using the function ID and language.
    A temporary build context is created and then cleaned up.

    :param function_id: Unique identifier of the function.
    :param language: Programming language ('python' or 'javascript').
    :param code: The user-supplied function code as a string.
    :return: A Docker image tag string.
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

#standard docker container
def warm_start_container(function_id: int, image_tag: str):
    """
    Start a warm container for the given function.
    The container is run with a command that keeps it alive (tail -f /dev/null)
    so that it can be reused for function execution.
    """
    try:
        print(f"[Pool] Warming up container for function {function_id} using image '{image_tag}'...")
        # Run the container in detached mode so that it stays alive.
        container = client.containers.run(image_tag, command="tail -f /dev/null", detach=True)
        return container
    except docker.errors.DockerException as de:
        print(f"[Pool] Error warming container: {str(de)}")
        raise de


def get_warm_container(function_id: int, image_tag: str):
    """
    Get an available warm container for the given function.
    If one does not exist in the pool, create a new one.
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



def run_function_in_pool(function_id: int, image_tag: str, language: str, timeout: int) -> dict:
    """
    Execute the function using a warm container from the pool.
    The function is executed via Docker's exec_run, and the container is
    returned to the pool after execution.
    """
    container = get_warm_container(function_id, image_tag)
    start_time = time.time()
    
    try:
        # Determine the command based on language.
        if language.lower() == "python":
            cmd = "python function.py"
        elif language.lower() == "javascript":
            cmd = "node function.js"
        else:
            raise ValueError("Unsupported language.")
        
        print(f"[Exec] Executing command '{cmd}' in container for function {function_id}.")
        
        # Run the function code within the container (without timeout parameter)
        exec_result = container.exec_run(cmd=cmd, demux=True)
        exit_code = exec_result.exit_code
        stdout, stderr = exec_result.output if exec_result.output else (b"", b"")
        execution_time = time.time() - start_time

        # Process the output.
        logs = (stdout.decode("utf-8") if stdout else "") + (stderr.decode("utf-8") if stderr else "")
        result = {
            "logs": logs,
            "execution_time": execution_time,
            "exit_code": exit_code
        }
    except Exception as e:
        result = {"error": str(e)}
        try:
            container.kill()
            container.remove()
        except Exception:
            pass
        return result

    # Return the container to the pool for reuse.
    return_container_to_pool(function_id, container)
    return result


### gVisor Container Pooling Functions
def warm_start_container_gvisor(function_id: int, image_tag: str):
    """
    Starts a warm container using gVisor by specifying the runtime 'runsc'.
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

def run_function_in_gvisor(function_id: int, image_tag: str, language: str, timeout: int) -> dict:
    container = get_warm_container_gvisor(function_id, image_tag)
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

        logs = (stdout.decode("utf-8") if stdout else "") + (stderr.decode("utf-8") if stderr else "")
        result = {
            "logs": logs,
            "execution_time": execution_time,
            "exit_code": exit_code
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

#def run_function_image(image_tag: str, timeout: int) -> dict:
#    """
#    Run the Docker container built from the image tag with a specified timeout.
#    The function waits for completion within the timeout window and then retrieves logs.
#
#    :param image_tag: The Docker image tag to run.
#    :param timeout: Maximum allowed execution time (in seconds).
#    :return: Dictionary containing container logs, execution time, and exit status.
#    """
#    try:
#        print(f"Running container from image '{image_tag}' with timeout {timeout} seconds...")
#        container = client.containers.run(image_tag, detach=True)
#
#        start_time = time.time()
#        exit_status = None
#
#        try:
#            # Wait for the container to finish.
#            exit_status = container.wait(timeout=timeout)
#        except Exception as e:
#            # If execution takes too long, kill container.
#            print(f"Execution timeout reached: {e}. Terminating container.")
#            container.kill()
#            return {"error": f"Function execution exceeded timeout of {timeout} seconds."}
#        finally:
#            execution_time = time.time() - start_time
#
#        # Retrieve container logs.
#        logs = container.logs().decode("utf-8")
#        # Remove the container after execution.
#        container.remove()
#        return {
#            "logs": logs,
#            "execution_time": execution_time,
#            "exit_code": exit_status.get("StatusCode") if exit_status else None
#        }
#    except docker.errors.DockerException as de:
#        return {"error": f"Docker error: {str(de)}"}
#
