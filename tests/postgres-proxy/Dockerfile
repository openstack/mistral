FROM haproxy:1.8.13-alpine

ENV CONF_DIR=/usr/local/etc/haproxy/ \
    PROXY_PORT=5433 \
    POSTGRES_URL=localhost:5432

COPY conf "${CONF_DIR}"

CMD haproxy -d -f /usr/local/etc/haproxy/haproxy.cfg
