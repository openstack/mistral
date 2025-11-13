FROM python:3.10.17-alpine3.22

WORKDIR /app
RUN echo 'https://dl-cdn.alpinelinux.org/alpine/v3.20/main/' > /etc/apk/repositories && \
    echo 'https://dl-cdn.alpinelinux.org/alpine/v3.20/community/' >> /etc/apk/repositories \
    apk update && apk add --no-cache \
    curl

COPY requirements.txt .

RUN pip install --upgrade pip==23.3 && pip install -r requirements.txt

# RUN pip install --upgrade pip==23.3 "setuptools==70.0.0"

COPY . .

EXPOSE 8000

ENV DEBUG_LOG=false \
    HOST=0.0.0.0 \
    PG_USER='postgres' \
    PG_PASSWORD="" \
    PG_HOST='postgres' \
    PG_PORT='5432' \
    PG_DB_NAME='mistral'\
    TLS_ENABLED=false

USER 1005000:1005000
RUN find / -perm /6000 -type f -exec chmod a-s {} \; || true

CMD ["python3", "main.py"]
