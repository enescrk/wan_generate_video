import runpod
from runpod.serverless.utils import rp_upload
import os
import websocket
import base64
import json
import uuid
import logging
import urllib.request
import urllib.parse
import binascii 
import subprocess
import time
import shutil

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

server_address = os.getenv('SERVER_ADDRESS', '127.0.0.1')
client_id = str(uuid.uuid4())

def to_nearest_multiple_of_16(value):
    try:
        numeric_value = float(value)
    except Exception:
        raise Exception(f"width/height 값이 숫자가 아닙니다: {value}")
    adjusted = int(round(numeric_value / 16.0) * 16)
    if adjusted < 16:
        adjusted = 16
    return adjusted

def process_input(input_data, temp_dir, output_filename, input_type):
    input_dir = "/ComfyUI/input"
    os.makedirs(input_dir, exist_ok=True)
    
    unique_filename = f"{temp_dir}_{output_filename}"
    file_path = os.path.join(input_dir, unique_filename)
    
    if input_type == "path":
        logger.info(f"📁 경로 입력 처리: {input_data}")
        if os.path.exists(input_data):
            shutil.copy(input_data, file_path)
            return unique_filename
        return input_data 
    elif input_type == "url":
        logger.info(f"🌐 URL 입력 처리: {input_data}")
        download_file_from_url(input_data, file_path)
        return unique_filename
    elif input_type == "base64":
        logger.info(f"🔢 Base64 입력 처리")
        save_base64_to_file(input_data, input_dir, unique_filename)
        return unique_filename
    else:
        raise Exception(f"지원하지 않는 입력 타입: {input_type}")

        
def download_file_from_url(url, output_path):
    try:
        result = subprocess.run([
            'wget', '-O', output_path, '--no-verbose', url
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"✅ URL에서 파일을 성공적으로 다운로드했습니다: {url} -> {output_path}")
            return output_path
        else:
            logger.error(f"❌ wget 다운로드 실패: {result.stderr}")
            raise Exception(f"URL 다운로드 실패: {result.stderr}")
    except subprocess.TimeoutExpired:
        logger.error("❌ 다운로드 시간 초과")
        raise Exception("다운로드 시간 초과")
    except Exception as e:
        logger.error(f"❌ 다운로드 중 오류 발생: {e}")
        raise Exception(f"다운로드 중 오류 발생: {e}")


def save_base64_to_file(base64_data, temp_dir, output_filename):
    try:
        decoded_data = base64.b64decode(base64_data)
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.abspath(os.path.join(temp_dir, output_filename))
        with open(file_path, 'wb') as f:
            f.write(decoded_data)
        
        logger.info(f"✅ Base64 입력을 '{file_path}' 파일로 저장했습니다.")
        return file_path
    except (binascii.Error, ValueError) as e:
        logger.error(f"❌ Base64 디코딩 실패: {e}")
        raise Exception(f"Base64 디코딩 실패: {e}")
    
def queue_prompt(prompt):
    url = f"http://{server_address}:8188/prompt"
    logger.info(f"Queueing prompt to: {url}")
    p = {"prompt": prompt, "client_id": client_id}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request(url, data=data)
    try:
        return json.loads(urllib.request.urlopen(req).read())
    except urllib.error.HTTPError as e:
        error_msg = e.read().decode('utf-8')
        logger.error(f"❌ ComfyUI API 에러 ({e.code}): {error_msg}")
        raise Exception(f"ComfyUI API Error {e.code}: {error_msg}")

def get_image(filename, subfolder, folder_type):
    url = f"http://{server_address}:8188/view"
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen(f"{url}?{url_values}") as response:
        return response.read()

def get_history(prompt_id):
    url = f"http://{server_address}:8188/history/{prompt_id}"
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read())

def get_videos(ws, prompt):
    prompt_id = queue_prompt(prompt)['prompt_id']
    output_videos = {}
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break
        else:
            continue

    history = get_history(prompt_id)[prompt_id]
    for node_id in history['outputs']:
        node_output = history['outputs'][node_id]
        videos_output = []
        if 'gifs' in node_output:
            for video in node_output['gifs']:
                video_path = video['fullpath']
                with open(video_path, 'rb') as f:
                    video_data = base64.b64encode(f.read()).decode('utf-8')
                videos_output.append(video_data)
                
                # --- TEMİZLİK: Üretilen videoyu diskten sil ---
                try:
                    os.remove(video_path)
                    logger.info(f"🗑️ Üretilen video silindi: {video_path}")
                except Exception as e:
                    logger.warning(f"⚠️ Video silinemedi: {e}")
                    
        output_videos[node_id] = videos_output

    return output_videos

def load_workflow(workflow_path):
    with open(workflow_path, 'r') as file:
        return json.load(file)

def handler(job):
    job_input = job.get("input", {})
    logger.info(f"Received job input: {job_input}")
    task_id = f"task_{uuid.uuid4()}"

    image_path = None
    if "image_path" in job_input:
        image_path = process_input(job_input["image_path"], task_id, "input_image.jpg", "path")
    elif "image_url" in job_input:
        image_path = process_input(job_input["image_url"], task_id, "input_image.jpg", "url")
    elif "image_base64" in job_input:
        image_path = process_input(job_input["image_base64"], task_id, "input_image.jpg", "base64")
    else:
        input_dir = "/ComfyUI/input"
        os.makedirs(input_dir, exist_ok=True)
        if os.path.exists("/example_image.png") and not os.path.exists(os.path.join(input_dir, "example_image.png")):
            shutil.copy("/example_image.png", os.path.join(input_dir, "example_image.png"))
        image_path = "example_image.png"

    end_image_path_local = None
    if "end_image_path" in job_input:
        end_image_path_local = process_input(job_input["end_image_path"], task_id, "end_image.jpg", "path")
    elif "end_image_url" in job_input:
        end_image_path_local = process_input(job_input["end_image_url"], task_id, "end_image.jpg", "url")
    elif "end_image_base64" in job_input:
        end_image_path_local = process_input(job_input["end_image_base64"], task_id, "end_image.jpg", "base64")
    
    lora_pairs = job_input.get("lora_pairs", [])
    lora_count = min(len(lora_pairs), 4)
    if lora_count > len(lora_pairs):
        lora_pairs = lora_pairs[:4]
    
    workflow_file = "/new_Wan22_flf2v_api.json" if end_image_path_local else "/new_Wan22_api.json"
    prompt = load_workflow(workflow_file)
    
    length = job_input.get("length", 81)
    steps = job_input.get("steps", 10)

    # --- ComfyUI Hatalarını Önlemek İçin Model Klasör Yollarını Düzeltme ---
    if "122" in prompt:
        prompt["122"]["inputs"]["model"] = "I2V/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors"
    if "549" in prompt:
        prompt["549"]["inputs"]["model"] = "I2V/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors"
    if "173" in prompt:
        prompt["173"]["inputs"]["clip_name"] = "split_files/clip_vision/clip_vision_h.safetensors"
    # ------------------------------------------------------------------------

    prompt["244"]["inputs"]["image"] = image_path
    prompt["541"]["inputs"]["num_frames"] = length
    prompt["135"]["inputs"]["positive_prompt"] = job_input["prompt"]
    prompt["135"]["inputs"]["negative_prompt"] = job_input.get("negative_prompt", "bright tones, overexposed, static, blurred details, subtitles, style, works, paintings, images, static, overall gray, worst quality, low quality, JPEG compression residue, ugly, incomplete, extra fingers, poorly drawn hands, poorly drawn faces, deformed, disfigured, misshapen limbs, fused fingers, still picture, messy background, three legs, many people in the background, walking backwards")
    prompt["220"]["inputs"]["seed"] = job_input["seed"]
    prompt["540"]["inputs"]["seed"] = job_input["seed"]
    prompt["540"]["inputs"]["cfg"] = job_input["cfg"]
    
    original_width = job_input["width"]
    original_height = job_input["height"]
    adjusted_width = to_nearest_multiple_of_16(original_width)
    adjusted_height = to_nearest_multiple_of_16(original_height)
    prompt["235"]["inputs"]["value"] = adjusted_width
    prompt["236"]["inputs"]["value"] = adjusted_height
    prompt["498"]["inputs"]["context_overlap"] = job_input.get("context_overlap", 48)
    prompt["498"]["inputs"]["context_frames"] = length

    if "834" in prompt:
        prompt["834"]["inputs"]["steps"] = steps
        lowsteps = int(steps*0.6)
        prompt["829"]["inputs"]["step"] = lowsteps

    if end_image_path_local:
        prompt["617"]["inputs"]["image"] = end_image_path_local
    
    if lora_count > 0:
        high_lora_node_id = "279"
        low_lora_node_id = "553"
        for i, lora_pair in enumerate(lora_pairs):
            if i < 4:
                lora_high = lora_pair.get("high")
                lora_low = lora_pair.get("low")
                lora_high_weight = lora_pair.get("high_weight", 1.0)
                lora_low_weight = lora_pair.get("low_weight", 1.0)
                
                # LoRA yollarını alt klasörleriyle düzeltme
                if lora_high:
                    if not lora_high.startswith("Wan2.2-I2V-A14B-4steps-lora-rank64-Seko-V1/"):
                        lora_high = f"Wan2.2-I2V-A14B-4steps-lora-rank64-Seko-V1/{lora_high}"
                    prompt[high_lora_node_id]["inputs"][f"lora_{i+1}"] = lora_high
                    prompt[high_lora_node_id]["inputs"][f"strength_{i+1}"] = lora_high_weight
                    
                if lora_low:
                    if not lora_low.startswith("Wan2.2-I2V-A14B-4steps-lora-rank64-Seko-V1/"):
                        lora_low = f"Wan2.2-I2V-A14B-4steps-lora-rank64-Seko-V1/{lora_low}"
                    prompt[low_lora_node_id]["inputs"][f"lora_{i+1}"] = lora_low
                    prompt[low_lora_node_id]["inputs"][f"strength_{i+1}"] = lora_low_weight

    ws_url = f"ws://{server_address}:8188/ws?clientId={client_id}"
    
    http_url = f"http://{server_address}:8188/"
    max_http_attempts = 180
    for http_attempt in range(max_http_attempts):
        try:
            import urllib.request
            response = urllib.request.urlopen(http_url, timeout=5)
            break
        except Exception as e:
            if http_attempt == max_http_attempts - 1:
                raise Exception("ComfyUI 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.")
            time.sleep(1)
    
    ws = websocket.WebSocket()
    max_attempts = int(180/5)
    for attempt in range(max_attempts):
        try:
            ws.connect(ws_url)
            break
        except Exception as e:
            if attempt == max_attempts - 1:
                raise Exception("웹소켓 연결 시간 초과 (3분)")
            time.sleep(5)
            
    videos = get_videos(ws, prompt)
    ws.close()

    # --- TEMİZLİK: Kullanılan input resimlerini sil ---
    input_dir = "/ComfyUI/input"
    for img_name in [image_path, end_image_path_local]:
        if img_name and img_name != "example_image.png":
            full_path = os.path.join(input_dir, img_name)
            try:
                if os.path.exists(full_path):
                    os.remove(full_path)
                    logger.info(f"🗑️ Input resmi silindi: {full_path}")
            except Exception as e:
                logger.warning(f"⚠️ Input resmi silinemedi: {e}")

    for node_id in videos:
        if videos[node_id]:
            return {"video": videos[node_id][0]}
    
    return {"error": "비디오를 찾을 수 없습니다."}

runpod.serverless.start({"handler": handler})
