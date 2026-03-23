# Use specific version of nvidia cuda image
# FROM wlsdml1114/my-comfy-models:v1 as model_provider
# FROM wlsdml1114/multitalk-base:1.7 as runtime
FROM wlsdml1114/engui_genai-base_blackwell:1.1 as runtime

ENV COMFYUI_DIR=/ComfyUI
ENV WORKSPACE_COMFYUI_DIR=/workspace/ComfyUI
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV GIT_CLONE_FLAGS="--depth 1"

RUN pip install -U --no-cache-dir "huggingface_hub[hf_transfer]"
RUN pip install --no-cache-dir runpod websocket-client

WORKDIR /

RUN git clone $GIT_CLONE_FLAGS https://github.com/comfyanonymous/ComfyUI.git "$COMFYUI_DIR" && \
    cd "$COMFYUI_DIR" && \
    pip install --no-cache-dir -r requirements.txt

RUN cd "$COMFYUI_DIR/custom_nodes" && \
    git clone $GIT_CLONE_FLAGS https://github.com/Comfy-Org/ComfyUI-Manager.git && \
    cd ComfyUI-Manager && \
    pip install --no-cache-dir -r requirements.txt
    
RUN cd "$COMFYUI_DIR/custom_nodes" && \
    git clone $GIT_CLONE_FLAGS https://github.com/city96/ComfyUI-GGUF && \
    cd ComfyUI-GGUF && \
    pip install --no-cache-dir -r requirements.txt

RUN cd "$COMFYUI_DIR/custom_nodes" && \
    git clone $GIT_CLONE_FLAGS https://github.com/kijai/ComfyUI-KJNodes && \
    cd ComfyUI-KJNodes && \
    pip install --no-cache-dir -r requirements.txt

RUN cd "$COMFYUI_DIR/custom_nodes" && \
    git clone $GIT_CLONE_FLAGS https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite && \
    cd ComfyUI-VideoHelperSuite && \
    pip install --no-cache-dir -r requirements.txt
    
RUN cd "$COMFYUI_DIR/custom_nodes" && \
    git clone $GIT_CLONE_FLAGS https://github.com/kael558/ComfyUI-GGUF-FantasyTalking && \
    cd ComfyUI-GGUF-FantasyTalking && \
    pip install --no-cache-dir -r requirements.txt
    
RUN cd "$COMFYUI_DIR/custom_nodes" && \
    git clone $GIT_CLONE_FLAGS https://github.com/orssorbit/ComfyUI-wanBlockswap && \
    git clone $GIT_CLONE_FLAGS https://github.com/Well-Made/ComfyUI-Wan-SVI2Pro-FLF.git

RUN cd "$COMFYUI_DIR/custom_nodes" && \
    git clone $GIT_CLONE_FLAGS https://github.com/kijai/ComfyUI-WanVideoWrapper && \
    cd ComfyUI-WanVideoWrapper && \
    pip install --no-cache-dir -r requirements.txt

    
RUN cd "$COMFYUI_DIR/custom_nodes" && \
    git clone $GIT_CLONE_FLAGS https://github.com/eddyhhlure1Eddy/IntelligentVRAMNode && \
    git clone $GIT_CLONE_FLAGS https://github.com/eddyhhlure1Eddy/auto_wan2.2animate_freamtowindow_server && \
    git clone $GIT_CLONE_FLAGS https://github.com/eddyhhlure1Eddy/ComfyUI-AdaptiveWindowSize && \
    cd ComfyUI-AdaptiveWindowSize/ComfyUI-AdaptiveWindowSize && \
    mv * ../

RUN cd "$COMFYUI_DIR/custom_nodes" && \
    git clone $GIT_CLONE_FLAGS https://github.com/ltdrdata/ComfyUI-Impact-Pack && \
    cd ComfyUI-Impact-Pack && \
    pip install --no-cache-dir -r requirements.txt

RUN cd "$COMFYUI_DIR/custom_nodes" && \
    git clone $GIT_CLONE_FLAGS https://github.com/ltdrdata/ComfyUI-Impact-Subpack && \
    cd ComfyUI-Impact-Subpack && \
    pip install --no-cache-dir -r requirements.txt

RUN cd "$COMFYUI_DIR/custom_nodes" && \
    git clone $GIT_CLONE_FLAGS https://github.com/brianfitzgerald/style_aligned_comfy

RUN cd "$COMFYUI_DIR/custom_nodes" && \
    git clone $GIT_CLONE_FLAGS https://github.com/MoonGoblinDev/Civicomfy

RUN cd "$COMFYUI_DIR/custom_nodes" && \
    git clone $GIT_CLONE_FLAGS https://github.com/Fannovel16/comfyui_controlnet_aux && \
    cd comfyui_controlnet_aux && \
    pip install --no-cache-dir -r requirements.txt

RUN cd "$COMFYUI_DIR/custom_nodes" && \
    git clone $GIT_CLONE_FLAGS https://github.com/storyicon/comfyui_segment_anything && \
    cd comfyui_segment_anything && \
    pip install --no-cache-dir -r requirements.txt

RUN cd "$COMFYUI_DIR/custom_nodes" && \
    git clone $GIT_CLONE_FLAGS https://github.com/yolain/ComfyUI-Easy-Use && \
    cd ComfyUI-Easy-Use && \
    pip install --no-cache-dir -r requirements.txt

RUN cd "$COMFYUI_DIR/custom_nodes" && \
    git clone $GIT_CLONE_FLAGS https://github.com/neeltheninja/ComfyUI-ComfyEnhancedMultiRegion

RUN cd "$COMFYUI_DIR/custom_nodes" && \
    git clone $GIT_CLONE_FLAGS https://github.com/PozzettiAndrea/ComfyUI-SAM3 && \
    cd ComfyUI-SAM3 && \
    pip install --no-cache-dir -r requirements.txt

RUN cd "$COMFYUI_DIR/custom_nodes" && \
    git clone $GIT_CLONE_FLAGS https://github.com/filliptm/ComfyUI-FL-Qwen3TTS && \
    cd ComfyUI-FL-Qwen3TTS && \
    pip install --no-cache-dir -r requirements.txt

# Patch ComfyUI-Impact-Pack to handle ComfyUI versions that expose SCHEDULER_NAMES
# instead of SCHEDULER_HANDLERS (compatibility fix for newer ComfyUI releases).
RUN python3 -c "\
import os; from pathlib import Path; \
path = Path(os.environ.get('COMFYUI_DIR', '/ComfyUI')) / 'custom_nodes/ComfyUI-Impact-Pack/modules/impact/core.py'; \
text = path.read_text(encoding='utf-8') if path.is_file() else None; \
old = 'def get_schedulers():\n    return list(comfy.samplers.SCHEDULER_HANDLERS) + ADDITIONAL_SCHEDULERS\n'; \
new = 'def get_schedulers():\n    handlers = getattr(comfy.samplers, \"SCHEDULER_HANDLERS\", None)\n    if handlers is None:\n        names = getattr(comfy.samplers, \"SCHEDULER_NAMES\", [])\n        return list(names) + ADDITIONAL_SCHEDULERS\n    return list(handlers) + ADDITIONAL_SCHEDULERS\n'; \
(text is not None and old in text) and path.write_text(text.replace(old, new), encoding='utf-8')"

COPY . .
COPY extra_model_paths.yaml ${COMFYUI_DIR}/extra_model_paths.yaml
RUN chmod +x /entrypoint.sh
RUN chmod +x /entrypoint-ui.sh

CMD ["/entrypoint.sh"]
