FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt -y update && apt -y upgrade && \
    apt -y install build-essential git m4 scons zlib1g zlib1g-dev \
    libprotobuf-dev protobuf-compiler libprotoc-dev libgoogle-perftools-dev \
    python3-dev doxygen libboost-all-dev libhdf5-serial-dev python3-pydot \
    libpng-dev libelf-dev pkg-config pip python3-venv wget tar

RUN pip install mypy pre-commit

# Set a working directory
WORKDIR /app

# Download and extract the gem5 source code
RUN wget https://github.com/gem5/gem5/archive/refs/tags/v22.1.0.0.tar.gz && \
    tar -xzf v22.1.0.0.tar.gz

RUN rm v22.1.0.0.tar.gz

WORKDIR /app/gem5-22.1.0.0

# This builds the X86 version. The "-j $(nproc)" part uses all available CPU cores.
RUN scons build/NULL/gem5.debug -j $(nproc) PROTOCOL=Garnet_standalone

WORKDIR /app

# Clone the Streamlit app from GitHub into the current directory
RUN git clone https://github.com/davin-san/garnet-web-visualizer.git

WORKDIR /app/garnet-web-visualizer

# Install the app's Python dependencies from its requirements.txt file
RUN pip install --no-cache-dir -r requirements.txt

# Expose the default Streamlit port so you can access it from your browser
EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

# Set the final command to run the Streamlit app
ENTRYPOINT ["streamlit", "run", "Home.py", "--server.port=8501", "--server.address=0.0.0.0"]