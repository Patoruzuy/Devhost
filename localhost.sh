#!/usr/bin/env bash

CADDYFILE="$HOME/.config/caddy/Caddyfile"

add() {
    name=$1
    port=$2

    if grep -q "${name}.localhost" "$CADDYFILE"; then
        echo "Domain already exists."
        return
    fi

    echo "${name}.localhost {
    reverse_proxy localhost:${port}
    tls internal
    encode gzip zstd
}" >> "$CADDYFILE"

    echo "Added ${name}.localhost → localhost:${port}"
    sudo systemctl reload caddy
}

remove() {
    name=$1
    sed -i "/^${name}.localhost {/,/^}/d" "$CADDYFILE"
    echo "Removed ${name}.localhost"
    sudo systemctl reload caddy
}

case "$1" in
  add)
    add $2 $3
    ;;
  remove)
    remove $2
    ;;
  *)
    echo "Usage: localhost {add|remove} app port"
    ;;
esac
