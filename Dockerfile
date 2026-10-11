FROM python:3.12.14-slim
WORKDIR /app
COPY requirements.txt .
RUN python -m pip install --only-binary=:all: -r requirements.txt
COPY . .
RUN python -m pip install --no-deps . && \
    if find wheelhouse -name '*.whl' -print -quit | grep -q .; then \
        python -m pip install --only-binary=:all: \
            "impulse-bot==$(python -c \
                'from importlib.metadata import version; print(version("impulse-bot"))')" \
            wheelhouse/*.whl; \
    fi
EXPOSE 5000

ENV DATA_PATH=/data
ENV CONFIG_PATH=/config

VOLUME /data
VOLUME /config

CMD ["python", "-m", "main"]
