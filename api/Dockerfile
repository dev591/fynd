# Backend only, for Railway (the website is deployed separately on Vercel). Build context is this folder (api/).
FROM python:3.13-slim
WORKDIR /srv/api
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . ./
# Railway sets PORT. SQLite lives on a mounted volume at /data so redeploys keep the data.
ENV CROSSOVER_DB=/data/app.db
RUN mkdir -p /data
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
