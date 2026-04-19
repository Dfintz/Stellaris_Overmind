FROM python:3.11-slim

WORKDIR /app

COPY engine/ engine/
COPY config.example.toml config.toml

# No heavy deps — stdlib only for core engine
# Optional: pip install tomli (for Python <3.11 TOML support)

CMD ["python", "-m", "engine.main"]
