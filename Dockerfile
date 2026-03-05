# Nome do arquivo: Dockerfile
FROM python:3.13-slim

# Instala dependências de sistema (minimalista)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Instala Poetry
RUN pip install --no-cache-dir poetry

WORKDIR /app

# Copia apenas o arquivo de dependências primeiro
COPY pyproject.toml /app/

# Instala dependências (se package-mode = false, talvez precise ajustar aqui)
RUN poetry config virtualenvs.create false \
    && poetry install --no-root --no-interaction --no-ansi

# Copia todo o resto (o .dockerignore filtrará automaticamente)
COPY . /app/

EXPOSE 8550 8001 8501

CMD ["python", "run.py"]