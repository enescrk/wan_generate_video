# Use specific version of nvidia cuda image
# FROM wlsdml1114/my-comfy-models:v1 AS model_provider
# FROM wlsdml1114/multitalk-base:1.7 AS runtime
FROM wlsdml1114/engui_genai-base_blackwell:1.1 AS runtime

RUN pip install -U "huggingface_hub[hf_transfer]"
RUN pip install runpod websocket-client

WORKDIR /

RUN git clone https://github.com/comfyanonymous/ComfyUI.git && \
    cd /ComfyUI && \
    pip install -r requirements.txt

RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/Comfy-Org/ComfyUI-Manager.git && \
    cd ComfyUI-Manager && \
    pip install -r requirements.txt
    
RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/city96/ComfyUI-GGUF && \
    cd ComfyUI-GGUF && \
    pip install -r requirements.txt

RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/kijai/ComfyUI-KJNodes && \
    cd ComfyUI-KJNodes && \
    pip install -r requirements.txt

RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite && \
    cd ComfyUI-VideoHelperSuite && \
    pip install -r requirements.txt
    
RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/kael558/ComfyUI-GGUF-FantasyTalking && \
    cd ComfyUI-GGUF-FantasyTalking && \
    pip install -r requirements.txt
    
RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/orssorbit/ComfyUI-wanBlockswap

RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/kijai/ComfyUI-WanVideoWrapper && \
    cd ComfyUI-WanVideoWrapper && \
    pip install -r requirements.txt

    
RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/eddyhhlure1Eddy/IntelligentVRAMNode && \
    git clone https://github.com/eddyhhlure1Eddy/auto_wan2.2animate_freamtowindow_server && \
    git clone https://github.com/eddyhhlure1Eddy/ComfyUI-AdaptiveWindowSize && \
    cd ComfyUI-AdaptiveWindowSize/ComfyUI-AdaptiveWindowSize && \
    mv * ../

# --- YENİ EKLENEN KISIM: hf_transfer ile CLI olmadan doğrudan Python üzerinden indirme ---
ENV HF_HUB_ENABLE_HF_TRANSFER=1

RUN python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='Kijai/WanVideo_comfy_fp8_scaled', filename='I2V/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors', local_dir='/ComfyUI/models/diffusion_models', local_dir_use_symlinks=False)"
RUN python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='Kijai/WanVideo_comfy_fp8_scaled', filename='I2V/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', local_dir='/ComfyUI/models/diffusion_models', local_dir_use_symlinks=False)"

RUN python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='lightx2v/Wan2.2-Lightning', filename='Wan2.2-I2V-A14B-4steps-lora-rank64-Seko-V1/high_noise_model.safetensors', local_dir='/ComfyUI/models/loras', local_dir_use_symlinks=False)"
RUN python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='lightx2v/Wan2.2-Lightning', filename='Wan2.2-I2V-A14B-4steps-lora-rank64-Seko-V1/low_noise_model.safetensors', local_dir='/ComfyUI/models/loras', local_dir_use_symlinks=False)"

RUN python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='Comfy-Org/Wan_2.1_ComfyUI_repackaged', filename='split_files/clip_vision/clip_vision_h.safetensors', local_dir='/ComfyUI/models/clip_vision', local_dir_use_symlinks=False)"
RUN python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='Kijai/WanVideo_comfy', filename='umt5-xxl-enc-bf16.safetensors', local_dir='/ComfyUI/models/text_encoders', local_dir_use_symlinks=False)"
RUN python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='Kijai/WanVideo_comfy', filename='Wan2_1_VAE_bf16.safetensors', local_dir='/ComfyUI/models/vae', local_dir_use_symlinks=False)"
# ------------------------------------------------------------------------------------------

COPY . .
COPY extra_model_paths.yaml /ComfyUI/extra_model_paths.yaml
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
