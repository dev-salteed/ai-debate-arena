# VSCode/Cursor 자동완성 설정 가이드

## 필수 확장 프로그램

### 1. **Python** (필수) ⭐
- ID: `ms-python.python`
- 기능: Python 언어 지원, 디버깅, 테스트
- 설치: Cursor에서 `Cmd+Shift+X` → "Python" 검색 → 설치

### 2. **Pylance** (필수) ⭐⭐⭐
- ID: `ms-python.vscode-pylance`
- 기능: **강력한 자동완성, 타입 체킹, IntelliSense**
- 이것이 핵심! 함수 추천, 파라미터 힌트, 자동 import 등

### 3. **IntelliCode** (선택, 추천) ⭐⭐
- ID: `visualstudioexptteam.vscodeintellicode`
- 기능: AI 기반 코드 완성 (사용 패턴 학습)

### 4. **GitHub Copilot** (선택, 유료) ⭐⭐⭐
- ID: `github.copilot`
- 기능: AI가 전체 함수/코드 블록 제안
- 월 $10 (학생/교육자 무료)

## 설치 방법

### 방법 1: Cursor UI에서 설치
```
1. Cmd+Shift+X (Extensions 열기)
2. "Python" 검색
3. Microsoft의 "Python" 확장 설치
4. "Pylance" 검색 → 설치
5. "IntelliCode" 검색 → 설치
```

### 방법 2: 명령어로 한 번에 설치
```bash
# 터미널에서 실행
cursor --install-extension ms-python.python
cursor --install-extension ms-python.vscode-pylance
cursor --install-extension visualstudioexptteam.vscodeintellicode
cursor --install-extension ms-python.black-formatter
```

## 자동완성 사용법

### 1. 기본 자동완성
```python
# "st" 입력 → Ctrl+Space → streamlit 선택
import streamlit as st

# "st." 입력 → 자동으로 메서드 목록 표시
st.title()  # ← title, text, write 등 제안됨
```

### 2. 파라미터 힌트
```python
# 함수명 입력 후 ( 입력하면 파라미터 정보 표시
st.text_input(  # ← label, value, max_chars 등 힌트 표시
```

### 3. 자동 Import
```python
# 함수 사용 → 자동으로 import 제안
response = ChatOpenAI()  # ← 상단에 import 추가 제안
```

### 4. 타입 힌트 기반 완성
```python
def process_data(df: pd.DataFrame):
    df.  # ← DataFrame의 모든 메서드 제안 (head, tail, groupby 등)
```

## 단축키

| 기능 | macOS | 설명 |
|------|-------|------|
| 자동완성 트리거 | `Ctrl+Space` | 제안 목록 강제 표시 |
| 파라미터 힌트 | `Cmd+Shift+Space` | 함수 파라미터 정보 |
| 정의로 이동 | `F12` | 함수/클래스 정의 보기 |
| 모든 참조 찾기 | `Shift+F12` | 사용된 곳 모두 보기 |
| Quick Fix | `Cmd+.` | 에러 자동 수정 제안 |

## 설정 확인

### Python 인터프리터 선택
```
1. Cmd+Shift+P
2. "Python: Select Interpreter" 입력
3. venv의 Python 선택 (./debate-prototype-XX/venv/bin/python)
```

### Pylance가 작동하는지 확인
```python
# 이 코드를 입력했을 때 자동완성이 나타나면 성공!
import streamlit as st
st.  # ← 여기서 메서드 목록이 보여야 함
```

## 문제 해결

### 자동완성이 안 나타나요?
1. Pylance가 설치되었는지 확인
2. Python 인터프리터가 venv로 선택되었는지 확인
3. `Cmd+Shift+P` → "Reload Window"

### Import를 인식 못해요?
1. 가상환경이 활성화되었는지 확인
2. `.vscode/settings.json`에서 `python.analysis.extraPaths` 확인
3. 패키지가 설치되었는지 확인: `pip3 list`

### 느려요?
1. `python.analysis.diagnosticMode`를 "openFilesOnly"로 변경
2. 큰 node_modules 폴더를 제외: `.gitignore`에 추가

## 추가 팁

### 1. 타입 힌트 사용하기
```python
# 타입 힌트를 사용하면 자동완성이 더 정확해집니다
def generate_response(prompt: str, temperature: float) -> str:
    # ...
```

### 2. Docstring 작성
```python
def my_function(param: str):
    """
    함수 설명을 작성하면
    사용할 때 힌트로 표시됩니다.
    
    Args:
        param: 파라미터 설명
    """
```

### 3. Stub 파일 활용
- 라이브러리의 타입 정보를 제공하는 파일
- Pylance가 자동으로 다운로드

## 현재 프로젝트 설정

이미 `.vscode/settings.json`에 다음 설정이 적용되었습니다:
- ✅ Pylance 활성화
- ✅ 자동 import 완성
- ✅ 함수 파라미터 자동 완성
- ✅ IntelliSense 최적화
- ✅ 모든 prototype 폴더 인식

이제 Cursor를 재시작하고 Python 파일을 열어보세요! 🚀
