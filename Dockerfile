# syntax=docker/dockerfile:1.7

ARG BASE_IMAGE=runpod/comfyui:latest
ARG ANIMA_LLLITE_REPO=https://github.com/kohya-ss/ComfyUI-Anima-LLLite.git
ARG ANIMA_LLLITE_REF=main
FROM ${BASE_IMAGE}
ARG ANIMA_LLLITE_REPO
ARG ANIMA_LLLITE_REF

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    U2NET_HOME=/root/.u2net

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        aria2 \
        ca-certificates \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /opt/anima-rmbg/requirements.txt
RUN PYTHON_BIN="$(command -v python3 || command -v python)" \
    && "${PYTHON_BIN}" -m pip install --no-cache-dir -r /opt/anima-rmbg/requirements.txt \
    && mkdir -p "${U2NET_HOME}" \
    && "${PYTHON_BIN}" -c "from rembg import new_session; new_session('isnet-general-use')"

RUN git clone --depth 1 --branch "${ANIMA_LLLITE_REF}" \
        "${ANIMA_LLLITE_REPO}" \
        /opt/anima-rmbg/ComfyUI-Anima-LLLite

COPY . /opt/anima-rmbg/custom_node/
RUN chmod +x /opt/anima-rmbg/custom_node/runpod/start.sh

EXPOSE 8188

ENTRYPOINT []
CMD ["/opt/anima-rmbg/custom_node/runpod/start.sh"]
