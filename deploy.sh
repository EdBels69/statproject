#!/bin/bash

set -e

echo "🚀 Starting deployment of Stat Analyzer..."

echo "📦 Step 1: Stopping existing containers..."
docker-compose down || true

echo "🧹 Step 2: Cleaning up old images..."
docker-compose build --no-cache

echo "🔨 Step 3: Building and starting containers..."
docker-compose up -d

echo "⏳ Step 4: Waiting for services to be ready..."
sleep 10

echo "🔍 Step 5: Checking service health..."
echo "Backend health check..."
for i in {1..30}; do
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ Backend is healthy!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Backend health check failed!"
        exit 1
    fi
    echo "Waiting for backend... ($i/30)"
    sleep 2
done

echo "Frontend check..."
if curl -f http://localhost:3000 > /dev/null 2>&1; then
    echo "✅ Frontend is running!"
else
    echo "⚠️ Frontend check failed, but may still be starting..."
fi

echo ""
echo "✨ Deployment completed successfully!"
echo ""
echo "🌐 Access URLs:"
echo "   Frontend: http://localhost:3000"
echo "   Backend API: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "📊 To view logs:"
echo "   docker-compose logs -f backend"
echo "   docker-compose logs -f frontend"
