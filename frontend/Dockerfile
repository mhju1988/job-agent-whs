# Stage 1 — deps
FROM node:20-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# Stage 2 — build
FROM node:20-slim AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Build-time NEXT_PUBLIC_* vars (baked into bundle)
ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY
ARG NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL
ENV NEXT_PUBLIC_SUPABASE_ANON_KEY=$NEXT_PUBLIC_SUPABASE_ANON_KEY
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
RUN mkdir -p /app/public && npm run build

# Stage 3 — runner
FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
# Next.js standalone reads HOSTNAME to decide what interface to bind.
# Without this the server binds to the container ID, not 0.0.0.0, and Railway's proxy can't reach it.
ENV HOSTNAME="0.0.0.0"
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
CMD ["node", "server.js"]
