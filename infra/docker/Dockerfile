# Dockerfile for BayanLab Community Data Backbone

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./
COPY backend/ ./backend/

# Install uv and dependencies
RUN pip install uv
RUN cd /app && uv pip install --system -e .

# Set Python path
ENV PYTHONPATH=/app/backend

# Expose port
EXPOSE 8000

# Default command (can be overridden by Railway)
CMD ["uvicorn", "backend.services.api_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
