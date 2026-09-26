FROM python:3.12-slim

WORKDIR /app

# Build tools for packages that occasionally need to compile (e.g. bcrypt on some platforms).
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Apply migrations, then start the API. DATABASE_URL, JWT_SECRET, GEMINI_API_KEY etc. are
# supplied by the host's environment/secret store at deploy time - see .env.example.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
