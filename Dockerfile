FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DB_PATH=/data/qr.db

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir flask==3.0.3 gunicorn==22.0.0 "qrcode[pil]==7.4.2"

COPY app.py .
COPY templates ./templates

RUN mkdir -p /data
VOLUME /data

EXPOSE 5000

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:5000/health').status==200 else 1)"

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "app:app"]
