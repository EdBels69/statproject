#!/bin/bash

set -e

echo "🛑 Stopping Stat Analyzer..."
docker-compose down

echo "🧹 Cleaning up..."
docker-compose down -v || true

echo "✅ Stopped successfully!"
