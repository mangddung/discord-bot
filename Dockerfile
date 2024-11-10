# 베이스 이미지로 Python 3.9 사용
FROM python:3.9-slim

# 작업 디렉토리 설정
WORKDIR /app

# 요구사항 파일을 복사
COPY requirements.txt .

# 필요한 패키지 설치
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 소스 코드 복사
COPY . .

# ffmpeg 설치
RUN apt-get update && apt-get install -y ffmpeg

# 컨테이너 시작 시 실행할 명령어
CMD ["python3", "discord_bot.py"]
