FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    BOT_CONFIG_PATH=config/config.railway.yaml

WORKDIR /app

COPY pyproject.toml ./
COPY bot ./bot
RUN pip install --no-cache-dir .

COPY data ./data
COPY config/config.railway.yaml ./config/config.railway.yaml

CMD ["python", "-m", "bot.main"]
