FROM ubuntu:22.04

# --- Static Build Steps (Runs only once when building the image) ---

ENV DEBIAN_FRONTEND=noninteractive
RUN apt -y update && apt -y upgrade && \
    apt -y install build-essential git m4 scons zlib1g zlib1g-dev \
    libprotobuf-dev protobuf-compiler libprotoc-dev libgoogle-perftools-dev \
    python3-dev doxygen libboost-all-dev libhdf5-serial-dev python3-pydot \
    libpng-dev libelf-dev pkg-config pip python3-venv wget tar

RUN pip install mypy pre-commit

# Set a working directory
WORKDIR /app

# Download and build gem5 (stable)
RUN wget https://github.com/gem5/gem5/archive/refs/tags/v22.1.0.0.tar.gz && \
    tar -xzf v22.1.0.0.tar.gz && \
    rm v22.1.0.0.tar.gz

WORKDIR /app/gem5-22.1.0.0
RUN scons build/NULL/gem5.debug -j $(nproc) PROTOCOL=Garnet_standalone

# Return to /app for the application code
WORKDIR /app

# OPTIMIZATION: Install dependencies during the build. 
# This is faster than installing every time the container starts.
# Temporarily clone the repo to get the requirements.txt, then remove it.
RUN git clone https://github.com/davin-san/garnet-web-visualizer.git /tmp/app-repo && \
    pip install --no-cache-dir -r /tmp/app-repo/requirements.txt && \
    rm -rf /tmp/app-repo

# Expose the default Streamlit port
EXPOSE 8501
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

# --- Dynamic Startup Step (Runs every time the container starts) ---

# The ENTRYPOINT executes these commands in a shell every time the container is run.
# 1. Checks if the directory exists.
# 2. If it exists, pulls the latest code.
# 3. If it doesn't exist, clones the repository.
# 4. Changes directory into the app.
# 5. Executes the main streamlit command.
ENTRYPOINT ( \
    if [ -d "garnet-web-visualizer" ]; then \
        echo "Pulling latest code..."; \
        cd garnet-web-visualizer && git pull origin main || git pull origin master; \
    else \
        echo "Cloning repository..."; \
        git clone https://github.com/davin-san/garnet-web-visualizer.git; \
        cd garnet-web-visualizer; \
    fi && \
    exec streamlit run Home.py --server.port=8501 \
)