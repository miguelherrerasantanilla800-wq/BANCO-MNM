FROM python:3.10

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY docker_exporter.py /app/docker_exporter.py
EXPOSE 9101
CMD ["python", "/app/docker_exporter.py"]
