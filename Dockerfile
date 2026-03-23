FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV COMFYUI_DIR=/ComfyUI
ENV WORKSPACE_COMFYUI_DIR=/workspace/ComfyUI
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV GIT_CLONE_FLAGS="--depth 1"

WORKDIR /

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        ffmpeg \
        git \
        libgl1 \
        libglib2.0-0 \
        python3 \
        python3-pip \
        wget && \
    ln -sf /usr/bin/python3 /usr/local/bin/python && \
    ln -sf /usr/bin/pip3 /usr/local/bin/pip && \
    python3 -m pip install --upgrade --no-cache-dir pip setuptools wheel && \
    python3 -m pip install --no-cache-dir \
        torch==2.8.0 \
        torchvision==0.23.0 \
        torchaudio==2.8.0 \
        --index-url https://download.pytorch.org/whl/cu128 && \
    python3 -m pip install --no-cache-dir \
        "huggingface_hub[hf_transfer]" \
        color-matcher \
        dill \
        einops \
        "gguf>=0.13.0" \
        imageio-ffmpeg \
        kornia \
        matplotlib \
        mss \
        opencv-python-headless \
        "pillow>=10.3.0" \
        piexif \
        protobuf \
        pyyaml \
        runpod \
        scipy \
        scikit-image \
        sentencepiece \
        "segment_anything" \
        timm \
        transformers \
        "ultralytics>=8.3.162" \
        websocket-client && \
    git clone $GIT_CLONE_FLAGS https://github.com/comfyanonymous/ComfyUI.git "$COMFYUI_DIR" && \
    python3 -m pip install --no-cache-dir -r "$COMFYUI_DIR/requirements.txt" && \
    mkdir -p "$COMFYUI_DIR/custom_nodes" && \
    git clone $GIT_CLONE_FLAGS https://github.com/city96/ComfyUI-GGUF "$COMFYUI_DIR/custom_nodes/ComfyUI-GGUF" && \
    git clone $GIT_CLONE_FLAGS https://github.com/kijai/ComfyUI-KJNodes "$COMFYUI_DIR/custom_nodes/ComfyUI-KJNodes" && \
    git clone $GIT_CLONE_FLAGS https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite "$COMFYUI_DIR/custom_nodes/ComfyUI-VideoHelperSuite" && \
    git clone $GIT_CLONE_FLAGS https://github.com/ltdrdata/ComfyUI-Impact-Pack "$COMFYUI_DIR/custom_nodes/ComfyUI-Impact-Pack" && \
    git clone $GIT_CLONE_FLAGS https://github.com/ltdrdata/ComfyUI-Impact-Subpack "$COMFYUI_DIR/custom_nodes/ComfyUI-Impact-Subpack" && \
    git clone $GIT_CLONE_FLAGS https://github.com/storyicon/comfyui_segment_anything "$COMFYUI_DIR/custom_nodes/comfyui_segment_anything" && \
    git clone $GIT_CLONE_FLAGS https://github.com/cubiq/ComfyUI_essentials "$COMFYUI_DIR/custom_nodes/ComfyUI_essentials" && \
    python3 -m pip install --no-cache-dir \
        addict \
        yapf && \
    apt-get purge -y --auto-remove git python3-pip && \
    rm -rf /root/.cache /var/lib/apt/lists/*

COPY . .
COPY extra_model_paths.yaml ${COMFYUI_DIR}/extra_model_paths.yaml
RUN chmod +x /entrypoint.sh /entrypoint-ui.sh

CMD ["/entrypoint.sh"]
