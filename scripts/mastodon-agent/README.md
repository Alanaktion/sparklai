# Mastodon Character Agent (Python scaffold)

This is a starter Python implementation for running a **single character** against Mastodon/GoToSocial.

## Features

- Single-character profile driven by text blocks (similar to `users` profile fields)
- Creates periodic posts
- Replies to public timeline posts (chance-based)
- Replies to mentions and direct mentions
- Includes ComfyUI **single-workflow** image generation scaffolding

## Setup

1. Create a Python environment (3.10+ recommended)
2. Install dependencies:

```bash
pip install -r scripts/mastodon-agent/requirements.txt
```

3. Copy env file and edit values:

```bash
cp scripts/mastodon-agent/.env.example .env
```

4. (Optional) If enabling images, create a ComfyUI workflow file at `COMFYUI_WORKFLOW_PATH` with shape:

```json
{
	"output_node_id": "9",
	"prompt": {
		"...": "...",
		"ckpt_name": "__MODEL__",
		"text": "__POSITIVE_PROMPT__"
	}
}
```

Supported placeholder values in workflow JSON:

- `__MODEL__`
- `__POSITIVE_PROMPT__`
- `__NEGATIVE_PROMPT__`
- `__WIDTH__`
- `__HEIGHT__`
- `__SEED__`
- `__FILENAME_PREFIX__`

5. Run:

```bash
python scripts/mastodon-agent/agent.py
```

## Notes

- This is intentionally minimal scaffolding to start migration work away from the current site/database flow.
- The script runs one character per process instance.
- If `ENABLE_IMAGE_GENERATION=true`, upload to Mastodon uses generated ComfyUI image bytes.
