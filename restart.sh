#!/bin/bash

set -e

echo "🔄 Restarting Stat Analyzer..."
./stop.sh
./deploy.sh
