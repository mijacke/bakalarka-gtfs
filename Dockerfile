FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

COPY requirements.txt README.md /app/
COPY agent_gtfs /app/agent_gtfs
COPY server_mcp_gtfs /app/server_mcp_gtfs
COPY data /app/data

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

CMD ["python", "-m", "agent_gtfs.api.api_server"]
