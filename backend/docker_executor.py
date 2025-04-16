import os
import time
import shutil
import tempfile
import docker

# Initialize docker client (make sure Docker is running and you have the python docker package installed)
client = docker.from_env()

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

def run_function_image(image_tag: str, timeout: int) -> dict:
    """
    Run the Docker container built from the image tag with a specified timeout.
    The function waits for completion within the timeout window and then retrieves logs.

    :param image_tag: The Docker image tag to run.
    :param timeout: Maximum allowed execution time (in seconds).
    :return: Dictionary containing container logs, execution time, and exit status.
    """
    try:
        print(f"Running container from image '{image_tag}' with timeout {timeout} seconds...")
        container = client.containers.run(image_tag, detach=True)

        start_time = time.time()
        exit_status = None

        try:
            # Wait for the container to finish.
            exit_status = container.wait(timeout=timeout)
        except Exception as e:
            # If execution takes too long, kill container.
            print(f"Execution timeout reached: {e}. Terminating container.")
            container.kill()
            return {"error": f"Function execution exceeded timeout of {timeout} seconds."}
        finally:
            execution_time = time.time() - start_time

        # Retrieve container logs.
        logs = container.logs().decode("utf-8")
        # Remove the container after execution.
        container.remove()
        return {
            "logs": logs,
            "execution_time": execution_time,
            "exit_code": exit_status.get("StatusCode") if exit_status else None
        }
    except docker.errors.DockerException as de:
        return {"error": f"Docker error: {str(de)}"}

