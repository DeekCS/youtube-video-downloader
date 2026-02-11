#!/bin/bash
# Start script for Railway deployment
# Railway runs docker-compose.yml services

set -e

echo "🚀 Starting YouTube Video Downloader services..."

# Start both backend and frontend services using docker-compose
docker-compose up --build
