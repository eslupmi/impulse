FROM python:3.12.3
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5000

ENV DATA_PATH=/data
ENV CONFIG_PATH=/config

VOLUME /data
VOLUME /config

CMD ["gunicorn", "-k", "eventlet", "-w", "1", "-b", "0.0.0.0:5000", "wsgi:app"]
