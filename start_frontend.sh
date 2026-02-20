#!/bin/bash
# Start the frontend development server

echo "🚀 Starting Frontend Development Server..."
echo "📍 UI will be available at: http://localhost:5173"
echo ""

cd "$(dirname "$0")/frontend"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "⚠️  Dependencies not installed. Installing..."
    npm install --legacy-peer-deps
fi

npm run dev




