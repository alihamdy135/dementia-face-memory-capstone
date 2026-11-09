FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 ffmpeg && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml requirements.txt ./
COPY src ./src
COPY models/download_models.py models/MODELS.md models/LICENSE-YUNET.txt models/LICENSE-SFACE.txt ./models/
COPY config ./config
RUN pip install --no-cache-dir . && python models/download_models.py --directory ./models
ENV FACE_MEMORY_MODEL_DIR=/app/models
ENV FACE_MEMORY_SETTINGS_PATH=/app/config/model-v1.json
ENV PORT=80
EXPOSE 80
CMD ["sh", "-c", "uvicorn face_memory.http_service:app --host 0.0.0.0 --port ${PORT:-80} --workers 1"]
