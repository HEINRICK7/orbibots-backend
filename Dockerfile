FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN adduser --disabled-password --gecos "" --uid 10001 app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY alembic.ini logging.conf ./
COPY migrations migrations
COPY src src
COPY deploy/entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh && chown -R app:app /app

USER app
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
