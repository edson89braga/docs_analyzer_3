# Nome do arquivo: Dockerfile
FROM python:3.13-slim

# Evita gravação de .pyc e buffer de logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry keyrings.alt

# Pré-baixa os dicionários do NLTK para não atrasar a análise de PDFs
RUN python -m pip install nltk \
    && python -m nltk.downloader punkt punkt_tab stopwords

WORKDIR /app

# Copia dependências primeiro para aproveitar o cache do Docker
COPY pyproject.toml /app/

RUN poetry config virtualenvs.create false \
    && poetry install --no-root --no-interaction --no-ansi

# Pré-instala os modelos ONNX do RapidOCR (evita download em runtime na VM, que não tem acesso
# direto à internet — ver NOTES_ocr.md). Os arquivos vêm de modelos_ocr/ (gitignorado, populado
# manualmente antes do build) e são copiados para dentro do pacote rapidocr já instalado.
COPY modelos_ocr/ /tmp/modelos_ocr/
RUN python -c "import rapidocr, os, shutil; \
    dest = os.path.join(os.path.dirname(rapidocr.__file__), 'models'); \
    os.makedirs(dest, exist_ok=True); \
    [shutil.copy(os.path.join('/tmp/modelos_ocr', f), dest) for f in os.listdir('/tmp/modelos_ocr')]" \
    && rm -rf /tmp/modelos_ocr

# Copia o código fonte
COPY . /app/

# Cria os diretórios necessários com permissões
RUN mkdir -p /app/data /app/uploads_temp && chmod -R 777 /app/data /app/uploads_temp

EXPOSE 8550

# O novo entrypoint focado em servidor
CMD ["python", "run_server.py"]