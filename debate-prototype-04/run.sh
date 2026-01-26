#!/bin/bash

# 색상 정의
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== AI Debate Arena - Prototype 04 ===${NC}"

# venv가 없으면 생성
if [ ! -d "venv" ]; then
    echo -e "${GREEN}Creating virtual environment...${NC}"
    python3 -m venv venv
fi

# venv 활성화
echo -e "${GREEN}Activating virtual environment...${NC}"
source venv/bin/activate

# 패키지 설치
echo -e "${GREEN}Installing dependencies...${NC}"
pip3 install -r requirements.txt

# Streamlit 실행
echo -e "${GREEN}Starting Streamlit app...${NC}"
streamlit run app/main.py
