#!/bin/sh
# Enciende el panel de riego si está apagado; lo apaga si está encendido.
DIR="$(dirname "$(readlink -f "$0")")"
PID=$(ss -ltnp 2>/dev/null | grep ':8000 ' | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2)
if [ -n "$PID" ]; then
  kill "$PID"
  notify-send "Riego" "Panel apagado"
else
  cd "$DIR" && setsid nohup python app.py >/tmp/riego.log 2>&1 &
  sleep 1.5
  notify-send "Riego" "Panel encendido en http://localhost:8000"
  xdg-open http://localhost:8000 >/dev/null 2>&1
fi
