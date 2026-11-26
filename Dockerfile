FROM ghcr.io/astral-sh/uv:0.13.1 AS uv
FROM python:3.11-slim-bookworm

COPY --from=uv /uv /uvx /usr/local/bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/workspace

# Git : la dépendance timesfm du groupe dl est récupérée depuis son dépôt.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 developer \
    && mkdir -p /workspace /opt/venv \
    && chown developer:developer /workspace /opt/venv
WORKDIR /workspace
USER developer

COPY --chown=developer:developer pyproject.toml uv.lock ./
RUN uv sync --locked --group dl

COPY --chown=developer:developer . .

# Environnement de développement : le futur lancement applicatif relève d'E5.
EXPOSE 8888 8501
CMD ["bash"]
