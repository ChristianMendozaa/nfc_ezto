FROM python:3.12-slim

WORKDIR /app

# Copiar requerimientos e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# Usa el puerto que proporciona Railway
ENV PORT=8000
EXPOSE 8000

# Uvicorn debe usar el puerto de entorno
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
