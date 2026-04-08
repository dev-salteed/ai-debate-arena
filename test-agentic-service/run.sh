#!/bin/bash

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== 오늘 뭐먹지 - Agentic Dining Service ===${NC}"

if [ ! -d "venv" ]; then
    echo -e "${GREEN}Creating virtual environment with Python 3.12...${NC}"
    python3.12 -m venv venv
fi

echo -e "${GREEN}Activating virtual environment...${NC}"
source venv/bin/activate

echo -e "${GREEN}Installing dependencies...${NC}"
pip install -r requirements.txt

echo -e "${GREEN}Starting Streamlit app...${NC}"
streamlit run app/main.py
