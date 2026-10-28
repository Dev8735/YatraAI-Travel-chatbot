FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

# Set INSTALL_ML=true to bake in sentence-transformers (multilingual embeddings, ~1 GB larger image).
ARG INSTALL_ML=false
COPY requirements.txt requirements-ml.txt ./
RUN pip install -r requirements.txt \
 && if [ "$INSTALL_ML" = "true" ]; then pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements-ml.txt; fi

COPY . .
RUN useradd --create-home --uid 10001 yatra && mkdir -p /app/data && chown -R yatra /app
USER yatra

EXPOSE 8000
# Migrations run automatically at startup (app.main lifespan).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
