# Setup Guide

Complete setup guide for deploying Amplifier App api.

## Quick Start

### 1. Directory Structure

Create the following directory structure:

```
workspace/
├── amplifier-core/           # Your fork
├── amplifier-foundation/     # Your fork
└── amplifier-app-api/      # This service
```

### 2. Fork Required Repositories

```bash
# On GitHub, fork these repositories:
# - https://github.com/microsoft/amplifier-core
# - https://github.com/microsoft/amplifier-foundation

# Clone your forks
cd workspace
git clone git@github.com:YOUR_USERNAME/amplifier-core.git
git clone git@github.com:YOUR_USERNAME/amplifier-foundation.git
git clone git@github.com:YOUR_USERNAME/amplifier-app-api.git
```

### 3. Install Dependencies

```bash
cd amplifier-app-api

# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project dependencies
uv pip install -e .
```

### 4. Configure Environment

```bash
# Copy example environment
cp .env.example .env

# Edit .env
nano .env
```

**Minimum required configuration:**

```bash
# API Keys (at least one)
ANTHROPIC_API_KEY=sk-ant-...
# OR
OPENAI_API_KEY=sk-...

# Local fork paths (default: ../amplifier-core and ../amplifier-foundation)
AMPLIFIER_CORE_PATH=../amplifier-core
AMPLIFIER_FOUNDATION_PATH=../amplifier-foundation
```

### 5. Run the Service

```bash
# Development mode with auto-reload
uvicorn amplifier_app_api.main:app --reload --host 0.0.0.0 --port 8765

# Or using the CLI script
amplifier-service
```

### 6. Verify Installation

```bash
# Check health
curl http://localhost:8765/health

# Should return:
# {"status": "healthy", "version": "0.1.0", "uptime_seconds": 5.2, "database_connected": true}

# Access API documentation
open http://localhost:8765/docs
```

## Docker Deployment

### 1. Build Image

```bash
docker build -t amplifier-app-api .
```

### 2. Run with Docker Compose

```bash
# Create .env with your configuration
cp .env.example .env
nano .env

# Start service
docker-compose up -d

# View logs
docker-compose logs -f amplifier-service

# Stop service
docker-compose down
```

### 3. Verify Docker Deployment

```bash
# Health check
docker-compose exec amplifier-service curl http://localhost:8765/health

# View logs
docker-compose logs -f
```

## Production Deployment

### Security Checklist

#### 1. Generate Secure Secret Key

```bash
# Generate a secure secret key
openssl rand -hex 32

# Add to .env
SECRET_KEY=<generated-key>
```

#### 2. Configure CORS

```bash
# In .env, set allowed origins
ALLOWED_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
```

#### 3. Set Up HTTPS

**Option A: Using Nginx**

```nginx
server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # For SSE streaming
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding off;
    }
}
```

**Option B: Using Caddy**

```
api.yourdomain.com {
    reverse_proxy localhost:8765
}
```

#### 4. Configure Database Persistence

```yaml
# In docker-compose.yml
volumes:
  amplifier-data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /data/amplifier
```

#### 5. Set Up Logging

```bash
# In .env
LOG_LEVEL=info

# Configure log rotation
sudo nano /etc/logrotate.d/amplifier-service
```

```
/var/log/amplifier-service/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
```

### Monitoring

#### Health Check Endpoint

```bash
# Add to your monitoring system
curl http://localhost:8765/health
```

#### Docker Health Check

Already configured in `Dockerfile`:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8765/health')"
```

#### Prometheus Metrics (Future Enhancement)

```python
# TODO: Add prometheus metrics endpoint
# GET /metrics
```

### Backup Strategy

```bash
# Backup database
cp ./amplifier.db ./backups/amplifier-$(date +%Y%m%d).db

# Backup session data
tar -czf ./backups/sessions-$(date +%Y%m%d).tar.gz ./sessions/

# Automated backup script
cat > /etc/cron.daily/amplifier-backup << 'EOF'
#!/bin/bash
BACKUP_DIR=/data/backups/amplifier
mkdir -p $BACKUP_DIR
cp /data/amplifier/amplifier.db $BACKUP_DIR/amplifier-$(date +%Y%m%d).db
tar -czf $BACKUP_DIR/sessions-$(date +%Y%m%d).tar.gz /data/amplifier/sessions/
# Keep only last 30 days
find $BACKUP_DIR -name "*.db" -mtime +30 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete
EOF
chmod +x /etc/cron.daily/amplifier-backup
```

## Upgrading Local Forks

Since this service uses local forks, you need to manually sync with upstream:

```bash
# Add upstream remotes (one-time setup)
cd ../amplifier-core
git remote add upstream https://github.com/microsoft/amplifier-core.git

cd ../amplifier-foundation
git remote add upstream https://github.com/microsoft/amplifier-foundation.git

# Sync with upstream
cd ../amplifier-core
git fetch upstream
git merge upstream/main

cd ../amplifier-foundation
git fetch upstream
git merge upstream/main

# Restart service to pick up changes
docker-compose restart amplifier-service
```

## Testing the Deployment

### 1. Create a Session

```bash
curl -X POST http://localhost:8765/sessions/create \
  -H "Content-Type: application/json" \
  -d '{"bundle": "foundation", "provider": "anthropic"}'
```

### 2. Send a Message

```bash
# Use session_id from previous response
curl -X POST http://localhost:8765/sessions/{session_id}/messages \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, Amplifier!"}'
```

### 3. List Sessions

```bash
curl http://localhost:8765/sessions
```

### 4. Check Configuration

```bash
curl http://localhost:8765/config
```

## Troubleshooting

### Service won't start

```bash
# Check logs
docker-compose logs amplifier-service

# Common issues:
# 1. Port 8765 already in use
lsof -ti:8765 | xargs kill

# 2. Database locked
rm amplifier.db
docker-compose restart
```

### Can't connect to database

```bash
# Check database file permissions
ls -la amplifier.db

# Recreate database
rm amplifier.db
docker-compose restart
```

### Local forks not found

```bash
# Verify paths
ls -la ../amplifier-core
ls -la ../amplifier-foundation

# Update .env with correct paths
AMPLIFIER_CORE_PATH=/absolute/path/to/amplifier-core
AMPLIFIER_FOUNDATION_PATH=/absolute/path/to/amplifier-foundation
```

### API returns 500 errors

```bash
# Check service logs
docker-compose logs -f amplifier-service

# Check health endpoint
curl http://localhost:8765/health

# Restart service
docker-compose restart
```

## Next Steps

- [ ] Set up CI/CD pipeline
- [ ] Configure monitoring and alerting
- [ ] Implement rate limiting
- [ ] Add authentication (JWT, OAuth)
- [ ] Set up multi-instance deployment with load balancer
- [ ] Configure auto-scaling
- [ ] Implement caching layer (Redis)

## Support

For issues and questions:
- Check the [README.md](README.md)
- Review API documentation at http://localhost:8765/docs
- Check [amplifier-app-cli documentation](https://github.com/microsoft/amplifier-app-cli)
