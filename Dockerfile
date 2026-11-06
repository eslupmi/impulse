FROM python:3.12.14-slim AS source
WORKDIR /source
COPY . .
ARG DEV_EDITION=community
RUN case "$DEV_EDITION" in \
      community) rm -rf enterprise ;; \
      enterprise) test -d enterprise ;; \
      *) echo "Invalid DEV_EDITION: $DEV_EDITION" >&2; exit 1 ;; \
    esac

FROM python:3.12.14-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY --from=source /source .
EXPOSE 5000

ARG DEV_EDITION=community
ENV DEV_EDITION=$DEV_EDITION
ENV DATA_PATH=/data
ENV CONFIG_PATH=/config

VOLUME /data
VOLUME /config

CMD ["python", "-m", "main"]
