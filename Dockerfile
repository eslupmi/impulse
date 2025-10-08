FROM python:3.12.10
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5000

ENV DATA_PATH=/data
ENV CONFIG_PATH=/config

VOLUME /data
VOLUME /config

CMD ["python", "-m", "main"]
