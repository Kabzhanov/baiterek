#!/usr/bin/env bash
# Подключает ЕППБ-стенд к боевому nginx bizdnai.com: location /baiterek/ -> 127.0.0.1:8080
# Идемпотентно: повторный запуск ничего не ломает. Reload только после успешного nginx -t.
set -euo pipefail

CONF=/etc/nginx/sites-enabled/bizdnai
BACKUP=/etc/nginx/sites-available/bizdnai.bak-baiterek-$(date +%Y%m%d-%H%M%S)

if grep -q 'location /baiterek/' "$CONF"; then
    echo "location /baiterek/ уже есть — ничего не меняю"
    exit 0
fi

cp "$CONF" "$BACKUP"
echo "бэкап: $BACKUP"

python3 - "$CONF" <<'PY'
import sys

path = sys.argv[1]
with open(path) as f:
    content = f.read()

block = """
    # EPPB MVP (конкурс Байтерек) — compose-стек на 127.0.0.1:8080
    location /baiterek/ {
        proxy_pass http://127.0.0.1:8080/baiterek/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
        client_max_body_size 20m;
    }
"""
marker = "server_name bizdnai.com www.bizdnai.com;"
idx = content.find(marker, content.find("listen 443"))
if idx == -1:
    sys.exit("не найден 443-блок bizdnai.com")
line_end = content.index("\n", idx) + 1
with open(path, "w") as f:
    f.write(content[:line_end] + block + content[line_end:])
print("конфиг пропатчен")
PY

if nginx -t; then
    systemctl reload nginx
    echo "nginx перезагружен — проверяю стенд…"
    sleep 1
    curl -fsS https://bizdnai.com/baiterek/api/health/ready && echo " — СТЕНД ЖИВОЙ: https://bizdnai.com/baiterek/take"
else
    echo "nginx -t УПАЛ — откатываю"
    cp "$BACKUP" "$CONF"
    nginx -t
    exit 1
fi
