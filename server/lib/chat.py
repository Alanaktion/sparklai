import json
import os
import tomllib
import requests

config = {}
if os.path.exists("config.toml"):
    with open("config.toml", "rb") as f:
        config = tomllib.load(f)

class OpenAIChat:
    api_url: str = config.get("chat-url", "http://127.0.0.1:1234/v1/")
    headers: dict[str,str] = {
        "Content-Type": "application/json",
    }

    # Model should be trained for tool use and capable of structured output
    model: str = config.get("chat-model", "qwen2.5-7b-instruct-1m")
    temperature: float = 0.7

    system_message: str|None = None
    response_schema: str|None = None

    def load_schema(self, schema=None):
        if schema is None:
            self.system_message = None
            self.response_schema = None
            return

        with open(f'schema/{schema}.txt') as file:
            self.system_message = file.read().strip()
        with open(f'schema/{schema}.schema.json') as file:
            self.response_schema = json.load(file)

    def schema_completion(self, schema, user_prompt, history=[]) -> dict:
        self.load_schema(schema)
        return self.completions(user_prompt, history) # type: ignore

    def completions(self, user_prompt, history=[]) -> str|dict:
        data = {
            "model": self.model,
            "messages": history + ([
                {"role": "user", "content": user_prompt},
            ] if user_prompt else []),
            "temperature": self.temperature,
        }

        if self.system_message:
            data['messages'].insert(-1, {"role": "system", "content": self.system_message})

        if self.response_schema:
            data["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "friends",
                    "strict": "true",
                    "schema": self.response_schema,
                }
            }

        response = requests.post(
            self.api_url + "chat/completions",
            headers=self.headers,
            json=data
        )
        response.raise_for_status()
        content = response.json().get("choices")[0].get("message").get("content")
        if self.response_schema:
            return json.loads(content)
        else:
            return content
