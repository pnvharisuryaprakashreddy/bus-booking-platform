#!/bin/sh
# Generates a local TLS certificate the first time the proxy starts.
# The key stays in the container writable layer and is not committed.
set -eu

mkdir -p /etc/nginx/certs
if [ ! -f /etc/nginx/certs/server.crt ] || [ ! -f /etc/nginx/certs/server.key ]; then
    openssl req -x509 -nodes -newkey rsa:2048 \
        -keyout /etc/nginx/certs/server.key \
        -out /etc/nginx/certs/server.crt \
        -days 365 \
        -subj "/CN=localhost/O=Bus Booking Local Demo"
    chmod 640 /etc/nginx/certs/server.key
fi

exec nginx -g "daemon off;"
