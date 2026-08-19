FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY bot ./bot
RUN pip install --no-cache-dir .
COPY config ./config
COPY data ./data
CMD ["python", "-m", "bot.main"]
