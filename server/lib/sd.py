import base64
import os
import tomllib
import requests

config = {}
if os.path.exists("config.toml"):
    with open("config.toml", "rb") as f:
        config = tomllib.load(f)

class SDImage:
    params: dict
    data: bytes

class StableDiffusion:
    url: str = config.get("sd-url", "http://127.0.0.1:7860/sdapi/v1/")
    model: str = config.get("sd-model", "dreamshaper_8")
    prompt_suffix: str = config.get("sd-prompt", "RAW photo,subject,8k uhd,dslr,high quality")
    negative_prompt: str = config.get("sd-negative-prompt", "nsfw,underexposed,underexposure,overexposure,overexposed,canvas frame,cartoon,3d,3d render,CGI,computer graphics")
    steps = 20
    sampler = "Euler a"
    img_format = "webp"

    def __init__(self):
        response = requests.post(self.url + 'options', json={
            "sd_model_checkpoint": self.model,
            "samples_format": self.img_format,
        })
        response.raise_for_status()

    def txt2img(self, prompt, height=512, width=512) -> SDImage:
        data = {
            'prompt': prompt + "\n" + self.prompt_suffix,
            'negative_prompt': self.negative_prompt,
            'num_inference_steps': self.steps,
            'height': height,
            'width': width,
            'seed': -1,
            'cfg_scale': 7,
            'steps': self.steps,
            # 'sampler': self.sampler,
            'restore_faces': True,
        }

        headers = {
            'Content-Type': 'application/json'
        }

        response = requests.post(self.url + 'txt2img', json=data, headers=headers)
        response_data = response.json()
        result = SDImage()
        result.params = response_data['parameters'], # type: ignore
        result.data = base64.b64decode(response_data['images'][0])
        return result

    def options(self):
        response = requests.get(self.url + 'options')
        return response.json()

    def unload(self):
        requests.post(self.url + 'unload-checkpoint')

    def reload(self):
        requests.post(self.url + 'reload-checkpoint')
