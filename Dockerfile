FROM python:3.11-alpine

# https://gist.github.com/mohanpedala/1e2ff5661761d3abd0385e8223e16425#set--o-pipefail
SHELL ["/bin/bash", "-eo", "pipefail", "-c"]

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /bot

COPY pyproject.toml poetry.lock

RUN pip install --no-cache-dir pip==23.0 poetry==1.3.2 && \
    poetry install --no-root

COPY . .

CMD poetry run mbfc-bot