FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libxrender1 libxext6 libsm6 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY mastercad/ ./mastercad/
COPY cloud_app.py ./
COPY web/ ./web/
RUN useradd --create-home --uid 10001 caduser && mkdir -p /tmp/mastercad-projects && chown -R caduser:caduser /app /tmp/mastercad-projects
USER caduser
ENV HOME=/home/caduser
EXPOSE 8080
CMD ["sh","-c","gunicorn cloud_app:app --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 2 --timeout 120 --access-logfile - --error-logfile -"]
