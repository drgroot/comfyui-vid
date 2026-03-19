FROM yusufali/comfyui:latest

RUN $COMFYUI_VENV_PIP install -U "huggingface_hub[hf_transfer]" runpod websocket-client

WORKDIR /

RUN cd "$COMFYUI_DIR/custom_nodes" && \
    git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite && \
    cd ComfyUI-VideoHelperSuite && \
    $COMFYUI_VENV_PIP install -r requirements.txt

RUN cd "$COMFYUI_DIR/custom_nodes" && \
    git clone https://github.com/kael558/ComfyUI-GGUF-FantasyTalking && \
    cd ComfyUI-GGUF-FantasyTalking && \
    $COMFYUI_VENV_PIP install -r requirements.txt

RUN cd "$COMFYUI_DIR/custom_nodes" && \
    git clone https://github.com/orssorbit/ComfyUI-wanBlockswap

RUN cd "$COMFYUI_DIR/custom_nodes" && \
    git clone https://github.com/eddyhhlure1Eddy/IntelligentVRAMNode && \
    git clone https://github.com/eddyhhlure1Eddy/auto_wan2.2animate_freamtowindow_server && \
    git clone https://github.com/eddyhhlure1Eddy/ComfyUI-AdaptiveWindowSize && \
    cd ComfyUI-AdaptiveWindowSize/ComfyUI-AdaptiveWindowSize && \
    mv * ../

RUN mkdir -p /workspace/ComfyUI/models && \
    rm -rf "$COMFYUI_DIR/models" && \
    ln -s /workspace/ComfyUI/models "$COMFYUI_DIR/models"

COPY . .

RUN chmod +x /entrypoint.sh /entrypoint-ui.sh

CMD ["/entrypoint.sh"]
