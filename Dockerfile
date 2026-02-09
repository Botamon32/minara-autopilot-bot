FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ bot/
COPY bot.py .

VOLUME ["/app/data"]
ENV DB_PATH=/app/data/state.db
ENV LOG_PATH=/app/data/bot.log

CMD ["python", "-u", "bot.py"]
