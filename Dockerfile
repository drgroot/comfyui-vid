# Use specific version of nvidia cuda image
# FROM wlsdml1114/my-comfy-models:v1 as model_provider
# FROM wlsdml1114/multitalk-base:1.7 as runtime
FROM wlsdml1114/engui_genai-base_blackwell:1.1 as runtime

ENV COMFYUI_DIR=/ComfyUI
ENV WORKSPACE_COMFYUI_DIR=/workspace/ComfyUI

RUN pip install -U "huggingface_hub[hf_transfer]"
RUN pip install runpod websocket-client

WORKDIR /

RUN git clone https://github.com/comfyanonymous/ComfyUI.git "$COMFYUI_DIR" && \
    cd "$COMFYUI_DIR" && \
    pip install -r requirements.txt

RUN cd "$COMFYUI_DIR/custom_nodes" && \
    git clone https://github.com/Comfy-Org/ComfyUI-Manager.git && \
    cd ComfyUI-Manager && \
    pip install -r requirements.txt
    
RUN cd "$COMFYUI_DIR/custom_nodes" && \
    git clone https://github.com/city96/ComfyUI-GGUF && \
    cd ComfyUI-GGUF && \
    pip install -r requirements.txt

RUN cd "$COMFYUI_DIR/custom_nodes" && \
    git clone https://github.com/kijai/ComfyUI-KJNodes && \
    cd ComfyUI-KJNodes && \
    pip install -r requirements.txt

RUN cd "$COMFYUI_DIR/custom_nodes" && \
    git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite && \
    cd ComfyUI-VideoHelperSuite && \
    pip install -r requirements.txt
    
RUN cd "$COMFYUI_DIR/custom_nodes" && \
    git clone https://github.com/kael558/ComfyUI-GGUF-FantasyTalking && \
    cd ComfyUI-GGUF-FantasyTalking && \
    pip install -r requirements.txt
    
RUN cd "$COMFYUI_DIR/custom_nodes" && \
    git clone https://github.com/orssorbit/ComfyUI-wanBlockswap

RUN cd "$COMFYUI_DIR/custom_nodes" && \
    git clone https://github.com/kijai/ComfyUI-WanVideoWrapper && \
    cd ComfyUI-WanVideoWrapper && \
    pip install -r requirements.txt

    
RUN cd "$COMFYUI_DIR/custom_nodes" && \
    git clone https://github.com/eddyhhlure1Eddy/IntelligentVRAMNode && \
    git clone https://github.com/eddyhhlure1Eddy/auto_wan2.2animate_freamtowindow_server && \
    git clone https://github.com/eddyhhlure1Eddy/ComfyUI-AdaptiveWindowSize && \
    cd ComfyUI-AdaptiveWindowSize/ComfyUI-AdaptiveWindowSize && \
    mv * ../

COPY . .
COPY extra_model_paths.yaml ${COMFYUI_DIR}/extra_model_paths.yaml
RUN chmod +x /entrypoint.sh
RUN chmod +x /entrypoint-ui.sh

CMD ["/entrypoint.sh"]
