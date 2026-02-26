# ─────────────────────────────────────────────
# Stage 1 — build React frontend
# ─────────────────────────────────────────────
FROM node:20-alpine AS react-build

WORKDIR /app/frontend_react
COPY frontend_react/package*.json ./
RUN npm install --silent

COPY frontend_react/ ./
RUN npm run build
# Output goes to /app/frontend/static/react  (see vite.config.js outDir)


# ─────────────────────────────────────────────
# Stage 2 — Python / Flask runtime
# ─────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# OS-level deps (needed for bcrypt / duckdb wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir flask-login bcrypt werkzeug

# Copy project source (excluding databases — they come via volume)
COPY . .

# Copy the React build from stage 1
COPY --from=react-build /app/frontend/static/react ./frontend/static/react

# Create data directories
RUN mkdir -p database

# Expose Flask port
EXPOSE 5000

# Entrypoint: initialise DBs if not present, then start Flask
CMD ["sh", "-c", "\
  [ -f database/users.db ]              || python database/create_user_db.py; \
  [ -f database/cpg_multi_tenant.duckdb ] || python database/create_multi_schema_demo.py; \
  python frontend/app_with_auth.py \
"]
