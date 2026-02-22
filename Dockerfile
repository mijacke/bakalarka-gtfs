FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_ROOT=/app

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml README.md /app/
COPY src /app/src
COPY config /app/config
COPY data /app/data

RUN pip install --no-cache-dir .

CMD ["python", "-m", "bakalarka_gtfs.api.server"]
