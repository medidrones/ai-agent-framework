FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258 AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY packages/atlas-agent-core /tmp/atlas-agent-core
COPY packages/atlas-agent-adapters /tmp/atlas-agent-adapters
COPY examples/kubernetes-recovery /tmp/atlas-kubernetes-recovery

RUN python -m pip wheel --no-cache-dir --wheel-dir /wheels \
      /tmp/atlas-agent-core \
      "/tmp/atlas-agent-adapters[postgresql,redis]" \
      /tmp/atlas-kubernetes-recovery

FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /opt/atlas

COPY --from=builder /wheels /wheels

RUN python -m pip install --no-cache-dir /wheels/*.whl \
    && rm -rf /wheels \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin atlas

USER 10001:10001
EXPOSE 8080

ENTRYPOINT ["atlas-kubernetes-worker"]
