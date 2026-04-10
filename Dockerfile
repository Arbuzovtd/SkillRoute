FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY skillroute_bot.py .
CMD ["python", "skillroute_bot.py"]