#!/bin/bash

# 색상 정의
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Generating Debate Graph PNG ===${NC}"

# venv 활성화
source venv/bin/activate

# PNG 생성
echo -e "${GREEN}Generating graph...${NC}"
PYTHONPATH=app python3 app/workflow/graph.py

# 결과 확인
if [ -f "debate_graph.png" ]; then
    echo -e "${GREEN}✅ Successfully generated: debate_graph.png${NC}"
    ls -lh debate_graph.png
else
    echo -e "\033[0;31m❌ Failed to generate graph${NC}"
    exit 1
fi
