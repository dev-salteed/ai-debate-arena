FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

EXPOSE 8000
EXPOSE 8501

# 기본 실행은 FastAPI 서버
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

