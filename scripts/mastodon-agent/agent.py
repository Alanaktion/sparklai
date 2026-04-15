import html
import json
import os
import random
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv
from mastodon import Mastodon, StreamListener
from openai import OpenAI

load_dotenv()


@dataclass
class CharacterProfile:
    name: str
    bio: str
    personality_traits: str
    interests: str
    writing_style: str
    backstory: str
    additional_prompt: str
    occupation: str
    relationship_status: str
    location: str


class ComfyClient:
    def __init__(self) -> None:
        self.base_url = os.getenv('COMFYUI_URL', '').rstrip('/')
        self.workflow_path = os.getenv('COMFYUI_WORKFLOW_PATH', '').strip()
        self.model = os.getenv('COMFYUI_MODEL', '').strip()
        self.enabled = bool(self.base_url and self.workflow_path)
        self.poll_interval = float(os.getenv('COMFYUI_POLL_INTERVAL_SECONDS', '1.5'))
        self.timeout = float(os.getenv('COMFYUI_TIMEOUT_SECONDS', '180'))
        self.default_width = int(os.getenv('COMFYUI_WIDTH', '1024'))
        self.default_height = int(os.getenv('COMFYUI_HEIGHT', '1024'))
        self.default_negative_prompt = os.getenv('COMFYUI_NEGATIVE_PROMPT', '').strip()
        self._workflow: dict[str, Any] | None = None

    def _url(self, path: str) -> str:
        return f'{self.base_url}/{path.lstrip("/")}'

    def _load_workflow(self) -> dict[str, Any]:
        if self._workflow is not None:
            return self._workflow
        workflow_raw = Path(self.workflow_path).read_text(encoding='utf-8')
        self._workflow = json.loads(workflow_raw)
        return self._workflow

    def _apply_placeholders(self, value: Any, replacements: dict[str, Any]) -> Any:
        if isinstance(value, str):
            return replacements.get(value, value)
        if isinstance(value, list):
            return [self._apply_placeholders(item, replacements) for item in value]
        if isinstance(value, dict):
            return {key: self._apply_placeholders(item, replacements) for key, item in value.items()}
        return value

    def generate(self, prompt: str, negative_prompt: str | None = None) -> tuple[bytes, str]:
        if not self.enabled:
            raise RuntimeError('ComfyUI is not configured')

        template = self._load_workflow()
        output_node_id = str(template['output_node_id'])
        workflow = template['prompt']
        seed = random.randint(0, 2147483647)
        replacements: dict[str, Any] = {
            '__MODEL__': self.model,
            '__POSITIVE_PROMPT__': prompt,
            '__NEGATIVE_PROMPT__': negative_prompt or self.default_negative_prompt,
            '__WIDTH__': self.default_width,
            '__HEIGHT__': self.default_height,
            '__SEED__': seed,
            '__FILENAME_PREFIX__': f'masto-agent-{int(time.time())}'
        }
        prompt_graph = self._apply_placeholders(workflow, replacements)

        submit = requests.post(
            self._url('prompt'),
            json={'prompt': prompt_graph, 'client_id': f'agent-{int(time.time())}'},
            timeout=30
        )
        submit.raise_for_status()
        prompt_id = submit.json().get('prompt_id')
        if not prompt_id:
            raise RuntimeError('ComfyUI did not return prompt_id')

        deadline = time.time() + self.timeout
        while time.time() < deadline:
            history = requests.get(self._url(f'history/{prompt_id}'), timeout=30)
            history.raise_for_status()
            body = history.json()
            entry = body.get(prompt_id, body)
            if entry.get('status', {}).get('status_str') == 'error':
                raise RuntimeError('ComfyUI workflow execution failed')

            outputs = entry.get('outputs', {})
            image = None
            if output_node_id in outputs and outputs[output_node_id].get('images'):
                image = outputs[output_node_id]['images'][0]
            else:
                for output in outputs.values():
                    images = output.get('images') if isinstance(output, dict) else None
                    if images:
                        image = images[0]
                        break

            if image:
                query = urlencode(
                    {
                        'filename': image.get('filename', ''),
                        'subfolder': image.get('subfolder', ''),
                        'type': image.get('type', 'output')
                    }
                )
                img = requests.get(self._url(f'view?{query}'), timeout=60)
                img.raise_for_status()
                mime_type = img.headers.get('content-type', 'image/webp').split(';', 1)[0]
                return img.content, mime_type

            time.sleep(self.poll_interval)

        raise RuntimeError('ComfyUI workflow timed out')


class MastodonCharacterAgent(StreamListener):
    def __init__(self, mastodon: Mastodon, ai_client: OpenAI, profile: CharacterProfile) -> None:
        super().__init__()
        self.masto = mastodon
        self.ai = ai_client
        self.profile = profile
        self.model = os.getenv('LLM_MODEL', 'llama3-70b-instruct')
        self.reply_chance = float(os.getenv('PUBLIC_REPLY_CHANCE', '0.2'))
        self.post_interval = int(os.getenv('POST_INTERVAL_SECONDS', '1800'))
        self.generate_images = os.getenv('ENABLE_IMAGE_GENERATION', 'false').lower() in {
            '1',
            'true',
            'yes'
        }
        self.comfy = ComfyClient()
        self.running = True

        me = self.masto.account_verify_credentials()
        self.my_acct = str(me.get('acct', '')).strip()
        self.max_characters = int(os.getenv('MASTODON_MAX_CHARACTERS', '0'))
        if self.max_characters <= 0:
            self.max_characters = self._fetch_instance_character_limit()

    def _fetch_instance_character_limit(self) -> int:
        try:
            instance = self.masto.instance()
            return int(instance['configuration']['statuses']['max_characters'])
        except (KeyError, TypeError, ValueError) as err:
            print(f'⚠️ Invalid instance character limit config, defaulting to 500: {err}')
            return 500
        except Exception as err:
            print(f'⚠️ Failed to fetch instance character limit, defaulting to 500: {err}')
            return 500

    def _clean_html(self, content: str) -> str:
        text = re.sub(r'<[^>]+>', ' ', content)
        return html.unescape(re.sub(r'\s+', ' ', text)).strip()

    def _system_prompt(self) -> str:
        blocks = [
            f'Character name: {self.profile.name}',
            f'Bio: {self.profile.bio}',
            f'Personality traits: {self.profile.personality_traits}',
            f'Interests: {self.profile.interests}',
            f'Writing style: {self.profile.writing_style}',
            f'Backstory: {self.profile.backstory}',
            f'Occupation: {self.profile.occupation}',
            f'Relationship status: {self.profile.relationship_status}',
            f'Location: {self.profile.location}',
            f'Additional prompt: {self.profile.additional_prompt}',
            'Keep replies concise, social, and in-character. Avoid roleplay tags and markdown.'
        ]
        return '\n'.join(blocks)

    def _chat(self, user_prompt: str) -> str:
        response = self.ai.chat.completions.create(
            model=self.model,
            messages=[
                {'role': 'system', 'content': self._system_prompt()},
                {'role': 'user', 'content': user_prompt}
            ],
            temperature=0.8
        )
        content = response.choices[0].message.content
        return (content or '').strip()

    def _safe_post(self, text: str, **kwargs: Any) -> None:
        if not text:
            return
        self.masto.status_post(status=text[: self.max_characters], **kwargs)

    def _maybe_generate_image(self, prompt: str) -> str | None:
        if not self.generate_images:
            return None
        if not self.comfy.enabled:
            print('⚠️ Image generation enabled but ComfyUI is not configured')
            return None
        try:
            data, mime_type = self.comfy.generate(prompt)
            media = self.masto.media_post(data, mime_type=mime_type, description='Generated image')
            return str(media['id'])
        except Exception as err:
            print(f'⚠️ Image generation failed: {err}')
            return None

    def create_post(self) -> None:
        prompt = 'Write one short social post that matches your voice and current mood.'
        text = self._chat(prompt)
        media_id = self._maybe_generate_image(f'{self.profile.name}: {text}')
        kwargs: dict[str, Any] = {}
        if media_id:
            kwargs['media_ids'] = [media_id]
        self._safe_post(text, visibility='public', **kwargs)
        print(f'📝 Posted: {text}')

    def reply_to_status(self, status: dict[str, Any], visibility: str) -> None:
        clean = self._clean_html(status.get('content', ''))
        acct = status['account']['acct']
        prompt = (
            f'Context: {visibility} conversation. '
            f'Reply to this post from @{acct}: "{clean}". '
            'Keep it natural and under 3 sentences.'
        )
        text = self._chat(prompt)
        reply = f'@{acct} {text}'.strip()
        self._safe_post(reply, in_reply_to_id=status['id'], visibility=visibility)
        print(f'💬 Replied to @{acct}: {text}')

    def on_update(self, status: dict[str, Any]) -> None:
        if status['account']['acct'] == self.my_acct:
            return
        clean = self._clean_html(status.get('content', ''))
        print(f"📢 Local post from {status['account']['acct']}: {clean}")
        if random.random() <= self.reply_chance:
            self.reply_to_status(status, 'public')

    def on_notification(self, notification: dict[str, Any]) -> None:
        if notification.get('type') != 'mention':
            return
        status = notification.get('status')
        if not status:
            return
        visibility = status.get('visibility', 'public')
        mode = 'DM' if visibility == 'direct' else 'Mention'
        print(f"📩 Received {mode} from {status['account']['acct']}")
        self.reply_to_status(status, visibility)

    def start_periodic_posts(self) -> threading.Thread:
        def _loop() -> None:
            while self.running:
                try:
                    self.create_post()
                except Exception as err:
                    print(f'⚠️ Post creation failed: {err}')
                time.sleep(self.post_interval)

        thread = threading.Thread(target=_loop, daemon=True)
        thread.start()
        return thread


if __name__ == '__main__':
    profile = CharacterProfile(
        name=os.getenv('CHARACTER_NAME', 'my-agent'),
        bio=os.getenv('CHARACTER_BIO', ''),
        personality_traits=os.getenv('CHARACTER_PERSONALITY_TRAITS', ''),
        interests=os.getenv('CHARACTER_INTERESTS', ''),
        writing_style=os.getenv('CHARACTER_WRITING_STYLE', ''),
        backstory=os.getenv('CHARACTER_BACKSTORY', ''),
        additional_prompt=os.getenv('CHARACTER_ADDITIONAL_PROMPT', ''),
        occupation=os.getenv('CHARACTER_OCCUPATION', ''),
        relationship_status=os.getenv('CHARACTER_RELATIONSHIP_STATUS', ''),
        location=os.getenv('CHARACTER_LOCATION', '')
    )

    ai_client = OpenAI(
        base_url=os.getenv('OPENAI_BASE_URL', 'http://127.0.0.1:1234/v1/'),
        api_key=os.getenv('OPENAI_API_KEY', 'no-key')
    )

    masto = Mastodon(
        access_token=os.getenv('MASTODON_ACCESS_TOKEN'),
        api_base_url=os.getenv('MASTODON_BASE_URL')
    )

    agent = MastodonCharacterAgent(masto, ai_client, profile)
    agent.start_periodic_posts()
    print('🚀 Agent started. Listening to user stream (mentions + home timeline)...')
    masto.stream_user(agent)
