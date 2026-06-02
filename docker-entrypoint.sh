#!/usr/bin/env bash
set -e

echo "Waiting for PostgreSQL at ${DB_HOST:-db}:${DB_PORT:-5432}…"
until python -c "import socket,os,sys; s=socket.socket(); s.settimeout(2); \
sys.exit(0 if s.connect_ex((os.getenv('DB_HOST','db'), int(os.getenv('DB_PORT','5432')))) == 0 else 1)" 2>/dev/null; do
  sleep 1
done
echo "PostgreSQL is up."

python manage.py migrate --noinput
python manage.py collectstatic --noinput

if [ "${SEED_DATA:-false}" = "true" ]; then
  echo "Seeding sample data…"
  python manage.py seed_data || true
fi

exec "$@"
