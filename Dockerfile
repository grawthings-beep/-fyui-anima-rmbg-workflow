# syntax=docker/dockerfile:1.7

ARG BASE_IMAGE=runpod/comfyui:latest
FROM ${BASE_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        aria2 \
        ca-certificates \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /opt/anima-rmbg/requirements.txt
RUN PYTHON_BIN="$(command -v python3 || command -v python)" \
    && "${PYTHON_BIN}" -m pip install --no-cache-dir -r /opt/anima-rmbg/requirements.txt

COPY . /opt/anima-rmbg/custom_node/
RUN chmod +x /opt/anima-rmbg/custom_node/runpod/start.sh

EXPOSE 8188

ENTRYPOINT []
CMD ["/opt/anima-rmbg/custom_node/runpod/start.sh"]
