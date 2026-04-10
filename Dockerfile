FROM python:3.12-slim
WORKDIR /app
COPY Requirements.txt .
RUN pip install --no-cache-dir -r Requirements.txt
COPY Skillroute_bot.py .
CMD ["python", "Skillroute_bot.py"]
