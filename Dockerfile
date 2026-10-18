# One container, one public address: the API serves the built website. https comes from the host, so the microphone
# and browser notifications work on every laptop. Supabase URL and anon key are public values needed at build time.
FROM node:20-alpine AS web
WORKDIR /web
COPY app/package.json app/package-lock.json ./
RUN npm ci
COPY app/ ./
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY
RUN npm run build

FROM python:3.13-slim
WORKDIR /srv
COPY api/requirements.txt ./api/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt
COPY api/ ./api/
COPY --from=web /web/dist ./app/dist
WORKDIR /srv/api
ENV PORT=8000 CROSSOVER_DB=/data/app.db
RUN mkdir -p /data
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
