FROM python:3.11-slim

WORKDIR /app

# system deps for httpx/uvicorn
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY router/requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY router/ .

EXPOSE 5555

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5555"]
