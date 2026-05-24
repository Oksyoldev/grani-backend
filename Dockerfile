FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --upgrade --no-cache-dir pymongo==4.9.2 motor==3.5.1

COPY . .

EXPOSE 8000

CMD ["uvicorn", "mongo_main:app", "--host", "0.0.0.0", "--port", "8000"]