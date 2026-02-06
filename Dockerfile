# Build stage for production dependencies
FROM node:lts-slim AS base
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable
COPY . /app
WORKDIR /app

# Install production dependencies only
FROM base AS prod-deps
RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm install --prod --frozen-lockfile

# Build the application
FROM base AS build
RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm install --frozen-lockfile
# Set temporary environment variables for the build process
# These will be overridden at runtime
ENV DATABASE_URL="file:/tmp/build.db"
ENV CHAT_URL="http://host.docker.internal:1234/v1/"
ENV CHAT_MODEL="meta-llama-3.1-8b-instruct"
ENV SD_URL="http://host.docker.internal:7860/sdapi/v1/"
ENV SD_PHOTO_MODEL="dreamshaper_8_93211"
ENV SD_PHOTO_PROMPT="RAW photo,8k uhd,dslr,high quality"
ENV SD_PHOTO_NEGATIVE_PROMPT="nsfw,underexposed,underexposure,overexposure,overexposed,canvas frame,cartoon,3d,3d render,CGI,computer graphics"
ENV SD_DRAWING_MODEL="rabbit_v7"
ENV SD_DRAWING_PROMPT="masterpiece,best quality,absurdres,highres"
ENV SD_DRAWING_NEGATIVE_PROMPT="3d,3d render,CGI,computer graphics"
ENV SD_STYLIZED_MODEL="restlessexistence_v30Reflection"
ENV SD_STYLIZED_PROMPT="(Maya 3d render:1.05),(masterpiece:1.3),(hires,high resolution:1.3),subsurface scattering,ambient occlusion,bloom"
ENV SD_STYLIZED_NEGATIVE_PROMPT="underexposed,underexposure,overexposure,overexposed,canvas frame,cartoon"
RUN pnpm run build

# Final production image
FROM node:lts-slim
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
ENV NODE_ENV=production

# Set default database URL (can be overridden via environment variables)
ENV DATABASE_URL="file:/data/local.db"

RUN corepack enable
WORKDIR /app

# Copy production dependencies and built application
COPY --from=prod-deps /app/node_modules /app/node_modules
COPY --from=build /app/build /app/build
COPY --from=build /app/package.json /app/package.json
COPY --from=build /app/drizzle.config.ts /app/drizzle.config.ts

# Create data directory for SQLite database
RUN mkdir -p /data && chown -R node:node /data /app

# Switch to non-root user for security
USER node

# Expose the default SvelteKit port
EXPOSE 3000

# Start the application
CMD ["node", "build"]
