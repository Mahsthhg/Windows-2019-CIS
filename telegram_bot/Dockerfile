FROM python:3.12-slim

# ffmpeg is required by yt-dlp for audio extraction & video merging.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Downloads go here (mount a volume if you want them to persist).
RUN mkdir -p downloads

CMD ["python", "run.py"]
