FROM python:3.12.14-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.22 /uv /uvx /bin/
WORKDIR /app
ENV UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
# Frozen resolution installs core without requiring sibling messenger checkouts.
RUN uv sync --frozen --no-dev --no-editable && \
    if find wheelhouse -name '*.whl' -print -quit | grep -q .; then \
        uv pip install --python .venv/bin/python "impulse-bot==$(.venv/bin/python -c 'from importlib.metadata import version; print(version("impulse-bot"))')" wheelhouse/*.whl; \
    fi
EXPOSE 5000

ENV PATH="/app/.venv/bin:$PATH"
ENV DATA_PATH=/data
ENV CONFIG_PATH=/config

VOLUME /data
VOLUME /config

CMD ["python", "-m", "main"]
