FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY processlens ./processlens
COPY web ./web
COPY samples ./samples
RUN useradd --create-home --uid 10001 app
USER app
EXPOSE 8810
HEALTHCHECK --interval=15s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8810/health')"
CMD ["python", "-m", "uvicorn", "processlens.api:app", "--host", "0.0.0.0", "--port", "8810"]
