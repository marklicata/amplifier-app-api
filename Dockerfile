# Multi-stage Dockerfile for Amplifier App api

FROM python:3.11-slim AS builder

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Set working directory
WORKDIR /build

# Copy project files
COPY pyproject.toml README.md ./
COPY amplifier_app_api ./amplifier_app_api

# Clean uv cache to ensure fresh git clones of dependencies
RUN uv cache clean

# Install dependencies (use regular install, not editable, for production)
RUN uv pip install --system .

# Production stage
FROM python:3.11-slim

# Install runtime dependencies including uv (needed for on-demand module installation)
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

# Create non-root user and directories
RUN useradd -m -u 1000 amplifier && \
    mkdir -p /data /home/amplifier/.cache/amplifier && \
    chown -R amplifier:amplifier /data /home/amplifier

# Copy installed packages and binaries from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/amplifier-service /usr/local/bin/amplifier-service

# Set working directory (but no source code here)
WORKDIR /data

# Switch to non-root user
USER amplifier

# Set environment variables for uv to use user installation
ENV UV_PYTHON_INSTALL_DIR=/home/amplifier/.local/uv/python
ENV UV_TOOL_DIR=/home/amplifier/.local/uv/tools
ENV UV_TOOL_BIN_DIR=/home/amplifier/.local/bin
ENV PATH="/home/amplifier/.local/bin:$PATH"

# Expose port
EXPOSE 8765

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8765/health')"

# Run the service
CMD ["amplifier-service"]
