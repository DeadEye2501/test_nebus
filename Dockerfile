FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv

RUN pip install --no-cache-dir "pipenv==2025.0.4"
COPY Pipfile Pipfile.lock ./
RUN pipenv install --system --deploy

COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app
