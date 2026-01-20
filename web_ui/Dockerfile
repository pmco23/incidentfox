FROM node:20-bookworm-slim AS base
WORKDIR /app

FROM base AS deps
COPY package.json package-lock.json ./
RUN npm ci
# Explicitly install platform-specific native binaries for linux/amd64
# These are needed because package-lock.json may be generated on a different platform
RUN npm install @next/swc-linux-x64-gnu lightningcss-linux-x64-gnu @tailwindcss/oxide-linux-x64-gnu --no-save || true

FROM base AS build
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-bookworm-slim AS runner
WORKDIR /app

# Install security patches
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

ENV NODE_ENV=production
ENV PORT=3000
ENV NEXT_TELEMETRY_DISABLED=1

# Next.js standalone output
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public

EXPOSE 3000
CMD ["node", "server.js"]
