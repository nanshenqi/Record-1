FROM swr.cn-east-3.myhuaweicloud.com/beosin-boom/uv:python3.11-bookworm-slim
ENV WORKDIR=/app \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

WORKDIR $WORKDIR
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-install-project

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

ENV PATH="$WORKDIR/.venv/bin:$PATH"
CMD ["python", "src/main.py"]
