FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY project/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY project /app/project

ENV PYTHONPATH=/app
EXPOSE 8000

CMD ["uvicorn", "project.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
