FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy application code into the chaos_tester package directory
# (the repo root IS the Python package, so gunicorn needs chaos_tester.app:app)
ARG CACHE_BUST=1
COPY . ./chaos_tester/

# Create reports directory inside the package
RUN mkdir -p chaos_tester/reports

# Cloud Run sets PORT env var (default 8080)
ENV PORT=8080

# Run with gunicorn for production
CMD exec gunicorn \
    --bind 0.0.0.0:$PORT \
    --workers 2 \
    --threads 4 \
    --timeout 120 \
    "chaos_tester.app:app"
