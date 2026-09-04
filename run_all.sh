#!/bin/bash

# Navigate to the project root directory
cd "$(dirname "$0")"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting all SIH components...${NC}"

# Function to handle cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down all services...${NC}"
    
    # Kill background jobs (frontend, backend, bot)
    kill $(jobs -p) 2>/dev/null
    
    # Stop Keycloak (optional, stopping it to keep system clean)
    echo -e "${CYAN}Stopping Keycloak Docker container...${NC}"
    (cd keycloak && docker compose down)
    
    echo -e "${GREEN}All services stopped.${NC}"
    exit 0
}

# Catch termination signals to cleanly shut down background processes
trap cleanup INT TERM

# 1. Start Keycloak (Docker Compose)
echo -e "${CYAN}[1/4] Starting Keycloak...${NC}"
(cd keycloak && docker compose up -d)
echo -e "${CYAN}Keycloak started in background.${NC}"

# 2. Start Backend (FastAPI)
echo -e "${BLUE}[2/4] Starting Backend (Port 8000)...${NC}"
(
    cd sih-backend
    if [ -d "venv" ]; then
        source venv/bin/activate
    fi
    # Install requirements just in case
    pip install -r requirements.txt -q
    uvicorn main:app --reload --port 8000
) &
BACKEND_PID=$!

# 3. Start Frontend (Vite/React)
echo -e "${YELLOW}[3/4] Starting Frontend...${NC}"
(
    cd sih-mobile-frontend
    npm install --silent
    npm run dev
) &
FRONTEND_PID=$!

# 4. Start Telegram Bot
echo -e "${GREEN}[4/4] Starting Telegram Bot...${NC}"
(
    cd sih-telegram-bot
    if [ -d "venv" ]; then
        source venv/bin/activate
    fi
    # Install requirements just in case
    pip install -r requirements.txt -q
    python bot.py
) &
BOT_PID=$!

echo -e "\n${GREEN}====================================================${NC}"
echo -e "${GREEN}All services are running!${NC}"
echo -e "Keycloak: http://localhost:8080"
echo -e "Backend:  http://localhost:8000"
echo -e "Frontend: Check the console output above for the port (usually http://localhost:5173)"
echo -e "${GREEN}====================================================${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop all services and exit.${NC}"

# Wait for background jobs to finish (they won't unless they crash or are killed)
wait $BACKEND_PID $FRONTEND_PID $BOT_PID
