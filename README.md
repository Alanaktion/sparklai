# SparklAI ✨

This is a fake social media site that generates all of its users, posts, images, and DMs with open source AI APIs like Llama and Stable Diffusion.

Front-end is a SvelteKit app, with source in `src/`, startable with `pnpm run dev`.

Do the thing first with `pnpm run db:push` to database it up.

## Docker Deployment

**Important:** The LLM and Stable Diffusion services must be accessible from within the Docker container. They cannot use `localhost` - use one of these options:
- **Included services** (default): The `docker-compose.yml` includes Ollama and Stable Diffusion services
- **Host services**: Use `host.docker.internal:PORT` to access services running on your host machine
- **External services**: Use third-party API endpoints (e.g., `https://api.openai.com/v1/` for OpenAI)
- **Container services**: Use Docker service names if running LLM/SD in other containers

### Using Docker Compose (Recommended)

The default `docker-compose.yml` includes everything you need to run SparklAI with Ollama and Stable Diffusion:

1. Download a Stable Diffusion model (first time only):
   
   The Stable Diffusion service requires at least one model file to be present before starting. You can download a model from Hugging Face:
   
   ```bash
   # Create the models directory
   docker volume create sd-models
   
   # Download a model (e.g., Stable Diffusion v1.5)
   # Option 1: Using a temporary container to download
   docker run --rm -v sd-models:/models alpine sh -c "\
     apk add --no-cache wget && \
     wget -O /models/Stable-diffusion/v1-5-pruned-emaonly.safetensors \
     https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors"
   
   # Option 2: Download locally and copy to volume
   # Download the model to your current directory first:
   wget https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors
   # Then copy to the volume:
   docker run --rm -v sd-models:/models -v $(pwd):/host alpine \
     sh -c "mkdir -p /models/Stable-diffusion && cp /host/v1-5-pruned-emaonly.safetensors /models/Stable-diffusion/"
   ```
   
   Alternative models you can use:
   - [Stable Diffusion v1.5](https://huggingface.co/runwayml/stable-diffusion-v1-5)
   - [Stable Diffusion v2.1](https://huggingface.co/stabilityai/stable-diffusion-2-1)
   - [Dreamshaper](https://huggingface.co/Lykon/DreamShaper) (recommended for better results)

2. Start all services:
   ```bash
   docker compose up -d
   ```

3. Pull the Ollama model (first time only):
   ```bash
   docker compose exec ollama ollama pull llama3.1:8b
   ```

4. Initialize the database (first time only):
   ```bash
   docker compose exec app sh -c "pnpm run db:push"
   ```

5. Access the application at http://localhost:3000

**Note:** The Stable Diffusion service requires an NVIDIA GPU by default. If you don't have a GPU, edit `docker-compose.yml` and remove the `deploy.resources.reservations` section for the `stable-diffusion` service.

### Using External Services

If you want to use external or host-based services instead of the included ones:

1. Copy `.env.docker.example` to `.env` and configure your environment variables:
   ```bash
   cp .env.docker.example .env
   ```

2. Edit `.env` to point to your LLM and Stable Diffusion services:
   - `CHAT_URL`: Your LLM API endpoint
     - For services on host: `http://host.docker.internal:1234/v1/`
     - For OpenAI: `https://api.openai.com/v1/` (set `OPENAI_API_KEY` as well)
   - `SD_URL`: Your Stable Diffusion API endpoint
     - For services on host: `http://host.docker.internal:7860/sdapi/v1/`
     - For external API: Use the full URL of your SD service

3. Start only the app service:
   ```bash
   docker compose up -d app
   ```

4. Initialize the database (first time only):
   ```bash
   docker compose exec app sh -c "pnpm run db:push"
   ```

5. Access the application at http://localhost:3000

### Using Docker Only

1. Build the Docker image:
   ```bash
   docker build -t sparklai .
   ```

2. Run the container:
   ```bash
   docker run -d \
     -p 3000:3000 \
     -v sparklai-data:/data \
     -e DATABASE_URL="file:/data/local.db" \
     -e CHAT_URL="http://host.docker.internal:1234/v1/" \
     -e CHAT_MODEL="meta-llama-3.1-8b-instruct" \
     -e SD_URL="http://host.docker.internal:7860/sdapi/v1/" \
     --name sparklai \
     sparklai
   ```

3. Initialize the database (first time only):
   ```bash
   docker exec sparklai sh -c "pnpm run db:push"
   ```

### Notes

- The SQLite database is persisted in a Docker volume at `/data/local.db`
- `host.docker.internal` allows the container to access services running on your host machine
- If your LLM/SD services are in other containers, use their service names instead
- For production, consider using environment-specific configuration files

### Production Deployment

For production deployments, use the `docker-compose.prod.yml` file:

```bash
docker compose -f docker-compose.prod.yml up -d
```

This configuration includes:
- Environment file support (`.env`)
- Health checks
- Security options (no-new-privileges)
- Resource limits (CPU and memory)
- Automatic restart policy

Make sure to create a `.env` file with your production configuration before deploying.

## Future

There are a few things that would really improve the realism/accuracy of the content generated:

- Define and inform the LLM of the relationship between specific users
- Allow human users to define their profile information, and provide it as context when generating responses
- Support multiple models and automatic switching between them based on the task
  - For example, different Stable Diffusion models depending on whether the image should be photorealistic, a drawing, an animated scene, etc.
- Allow human users to see/edit user metadata used by the LLM
