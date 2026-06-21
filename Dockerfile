# Devin's Younger Brother — Multi-service image (Python 3.10)
# Used by docker-compose for both FastAPI backend and Streamlit frontend.
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    DYB_SANDBOX_DIR=/tmp/devin_brother_sandbox

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py main.py ./
COPY src ./src

RUN mkdir -p "${DYB_SANDBOX_DIR}"

# FastAPI backend (8000) and Streamlit frontend (8501)
EXPOSE 8000 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health')" || exit 1

# Default CMD runs Streamlit; docker-compose overrides for the API service.
CMD ["python", "-m", "streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
