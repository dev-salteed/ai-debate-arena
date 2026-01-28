# Python 버전 정보

## 현재 사용 중인 Python 버전

**Python 3.12.12** (2026년 1월 26일 설정)

## 변경 이력

### 2026-01-26
- ❌ Python 3.14.2 제거
  - 이유: Langfuse 및 Pydantic V1이 Python 3.14를 지원하지 않음
  - 에러: `RuntimeError: no validator found for <class 'pydantic.v1.fields.UndefinedType'>`
  
- ✅ Python 3.12.12 설치
  - 안정성: 대부분의 라이브러리가 지원
  - 호환성: Langfuse, LangChain, Streamlit 모두 호환

## 설치 방법

```bash
# Python 3.12 설치
brew install python@3.12

# 버전 확인
python3.12 --version
```

## 권장 사항

- **프로덕션 환경**: Python 3.11 또는 3.12 사용
- **개발 환경**: Python 3.12 사용 (현재 설정)
- **피해야 할 버전**: Python 3.14+ (너무 최신, 라이브러리 지원 부족)

## 프로젝트별 Python 설정

모든 `run.sh` 스크립트가 Python 3.12를 명시적으로 사용하도록 설정됨:
```bash
python3.12 -m venv venv
```

## VSCode/Cursor 설정

`.vscode/settings.json`에서 Python 3.12 인터프리터 사용 설정:
```json
"python.defaultInterpreterPath": "${workspaceFolder}/debate-prototype-01/venv/bin/python3.12"
```
