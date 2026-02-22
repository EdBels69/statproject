# 🚀 Deployment Guide

For Windows 11 deployment, use [DEPLOYMENT_WIN11.md](DEPLOYMENT_WIN11.md).

## 📋 Prerequisites

- Docker (>= 20.10)
- Docker Compose (>= 2.0)
- 4GB+ RAM
- 10GB+ disk space

## 🚀 Quick Start

### 1. Clone the repository

```bash
git clone <repository-url>
cd statproject
```

### 2. Run preflight checks (recommended)

```bash
./deploy_preflight.sh
```

For full backend regression before release:

```bash
./deploy_preflight.sh full
```

### 3. Deploy the application

```bash
./deploy.sh
```

That's it! The application will be available at:
- **Frontend**: http://localhost:3100
- **Backend API**: http://localhost:8100
- **API Documentation**: http://localhost:8100/docs

## 📦 Docker Services

### Backend (FastAPI)
- **Port**: 8100
- **Health Check**: http://localhost:8100/health
- **Workers**: 4 (Gunicorn + Uvicorn)
- **Timeout**: 120 seconds

### Frontend (React + Nginx)
- **Port**: 3100
- **Proxy**: API requests proxied to backend

## 🔧 Manual Deployment

### Build containers

```bash
docker-compose build
```

### Start services

```bash
docker-compose up -d
```

### Stop services

```bash
./stop.sh
# or
docker-compose down
```

### Restart services

```bash
./restart.sh
# or
docker-compose restart
```

### View logs

```bash
# All services
docker-compose logs -f

# Backend only
docker-compose logs -f backend

# Frontend only
docker-compose logs -f frontend
```

## 🌐 Production Deployment

### Environment Variables

#### Backend (.env.production)
```bash
DATA_DIR=/app/workspace/datasets
PYTHONUNBUFFERED=1
LOG_LEVEL=INFO
MAX_UPLOAD_SIZE=52428800
ALLOWED_EXTENSIONS=.csv,.xlsx,.xls
BACKEND_CORS_ORIGINS=http://localhost:3100,http://localhost:8080
```

#### Frontend (.env.production)
```bash
VITE_API_URL=http://localhost:8100
VITE_APP_TITLE=Stat Analyzer
```

### Custom Ports

Use environment overrides:

```bash
BACKEND_PORT=8200 FRONTEND_PORT=3200 docker compose up -d --build
```

Or edit `docker-compose.yml`:

```yaml
services:
  backend:
    ports:
      - "${BACKEND_PORT:-8100}:8000"
  
  frontend:
    ports:
      - "${FRONTEND_PORT:-3100}:80"
```

### SSL/HTTPS (Nginx Proxy)

For production, use a reverse proxy with SSL:

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:3100;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /api {
        proxy_pass http://localhost:8100;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 🔍 Troubleshooting

### Backend not starting

```bash
# Check logs
docker-compose logs backend

# Check health
curl http://localhost:8100/health

# Restart
docker-compose restart backend
```

### Frontend showing 502 Bad Gateway

```bash
# Check if backend is healthy
curl http://localhost:8100/health

# Check nginx logs
docker-compose logs frontend
```

### Build errors

```bash
# Clean build
docker-compose build --no-cache

# Remove volumes
docker-compose down -v

# Rebuild
docker-compose up -d --build
```

### Port already in use

```bash
# Check what's using the port
lsof -i :3100
lsof -i :8100

# Kill the process
kill -9 <PID>
```

## 📊 Monitoring

### Check container status

```bash
docker-compose ps
```

### Resource usage

```bash
docker stats
```

### Health checks

```bash
# Backend health
curl http://localhost:8100/health

# API documentation
curl http://localhost:8100/openapi.json
```

## 🔒 Security Considerations

1. **Change default ports** in production
2. **Use SSL/TLS** for all connections
3. **Restrict CORS origins** in backend configuration
4. **Set resource limits** in docker-compose.yml:

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
```

## 📈 Scaling

### Multiple backend instances

```yaml
services:
  backend:
    deploy:
      replicas: 3
```

### Load balancer

Use Nginx or HAProxy to distribute traffic across backend instances.

## 🔄 Updates

### Update application

```bash
git pull
./restart.sh
```

### Update Docker images

```bash
docker-compose pull
docker-compose up -d
```

## 📝 Development

### Run in development mode

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## 🆘 Support

For issues and questions:
- Check logs: `docker-compose logs -f`
- Verify health: `curl http://localhost:8100/health`
- Review docs: http://localhost:8100/docs

## ✅ Health Checklist

- [ ] Docker and Docker Compose installed
- [ ] Ports 3000 and 8000 are available
- [ ] Environment variables configured
- [ ] Containers are running: `docker-compose ps`
- [ ] Backend health check passes: `curl http://localhost:8100/health`
- [ ] Frontend accessible: `curl http://localhost:3100`
- [ ] API documentation available: `http://localhost:8100/docs`
