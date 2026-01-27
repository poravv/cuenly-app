# Usar imagen oficial de Docker Hub
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# Instalar Tesseract OCR y dependencias del sistema
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-spa \
    tesseract-ocr-eng \
    poppler-utils \
    build-essential \
    curl \
    libmagic1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Establecer directorio de trabajo
WORKDIR /app

# Crear directorios necesarios
RUN mkdir -p /app/data/temp_pdfs

# Copiar archivos de requerimientos
COPY requirements.txt .

# Instalar dependencias Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir numpy==1.24.3 && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir spacy==3.6.1

# Descargar modelos de spaCy de forma más robusta
RUN python -c "import spacy; spacy.cli.download('es_core_news_md')" && \
    python -c "import spacy; spacy.cli.download('en_core_web_md')"

# Copiar código fuente
COPY . .

# Establecer variables de entorno
ENV PYTHONPATH=/app
ENV TESSERACT_PATH=/usr/bin/tesseract

# Exponer puerto
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Comando por defecto
CMD ["python", "app/server.py"]
