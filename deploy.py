#!/usr/bin/env python3
"""
Deploy script for Stat Analyzer MVP
Run this script to deploy the application using Docker
"""

import subprocess
import sys
import time

def run_command(cmd, description):
    """Execute a command and return success status"""
    print(f"\n{'='*60}")
    print(f"🔄 {description}")
    print(f"{'='*60}")
    print(f"Command: {cmd}")
    print()
    
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=True,
            capture_output=False,
            text=True
        )
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed with error:")
        print(e)
        return False

def main():
    print("\n" + "="*60)
    print("🚀 Stat Analyzer MVP - Deployment Script")
    print("="*60)
    
    # Check if Docker is installed
    print("\n🔍 Checking Docker installation...")
    if not run_command("docker --version", "Docker version check"):
        print("\n❌ Docker is not installed or not accessible!")
        print("Please install Docker Desktop from https://www.docker.com/products/docker-desktop")
        sys.exit(1)
    
    # Check if Docker Compose is available
    print("\n🔍 Checking Docker Compose...")
    if not run_command("docker-compose --version", "Docker Compose version check"):
        print("\n❌ Docker Compose is not available!")
        sys.exit(1)
    
    # Stop any running containers
    print("\n🛑 Stopping any running containers...")
    run_command("docker-compose down", "Stop existing containers")
    
    # Build and start services
    print("\n🔨 Building and starting services...")
    if not run_command("docker-compose up -d --build", "Build and start services"):
        print("\n❌ Failed to start services!")
        sys.exit(1)
    
    # Wait for services to be healthy
    print("\n⏳ Waiting for services to be healthy...")
    time.sleep(5)
    
    # Check service status
    print("\n📊 Checking service status...")
    run_command("docker-compose ps", "Service status")
    
    # Check backend health
    print("\n🏥 Checking backend health...")
    for attempt in range(5):
        try:
            result = subprocess.run(
                "curl -s http://localhost:8000/health",
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                print(f"✅ Backend health check passed:")
                print(result.stdout)
                break
        except Exception as e:
            print(f"⚠️  Health check attempt {attempt + 1}/5 failed...")
            time.sleep(2)
    else:
        print("⚠️  Backend health check failed, but containers are running")
    
    # Show logs
    print("\n📋 Recent logs:")
    run_command("docker-compose logs --tail=20", "Recent logs")
    
    # Display access URLs
    print("\n" + "="*60)
    print("✅ Deployment completed successfully!")
    print("="*60)
    print("\n🌐 Access URLs:")
    print("  - Frontend:  http://localhost:3000")
    print("  - Backend:   http://localhost:8000")
    print("  - API Docs:  http://localhost:8000/docs")
    print("  - Health:    http://localhost:8000/health")
    print("\n📝 Useful commands:")
    print("  - View logs:     docker-compose logs -f")
    print("  - Stop services: docker-compose down")
    print("  - Restart:       docker-compose restart")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
