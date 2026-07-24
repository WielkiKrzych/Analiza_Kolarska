#!/bin/bash
# launcher.sh — Analiza Kolarska Streamlit lifecycle manager
# Called by the macOS .app wrapper built by build_app.sh.
#
# Logs go to /tmp/ (TCC on recent macOS blocks applets writing to ~/Documents).

export PATH="$HOME/.local/bin:$HOME/Library/Python/3.14/bin:$HOME/Library/Python/3.13/bin:$HOME/Library/Python/3.12/bin:$HOME/Library/Python/3.11/bin:$HOME/Library/Python/3.10/bin:/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

APP_DIR="$HOME/Documents/Analiza_Kolarska"
LOG="/tmp/analiza_kolarska_launch.log"
PORT=8502
URL="http://localhost:$PORT"

exec > "$LOG" 2>&1
echo "[launcher] $(date) Started"

# ---- Find streamlit binary ----
STREAMLIT_BIN=""
for candidate in \
  "$HOME/Library/Python/3.14/bin/streamlit" \
  "$HOME/Library/Python/3.13/bin/streamlit" \
  "$HOME/Library/Python/3.12/bin/streamlit" \
  "$HOME/Library/Python/3.11/bin/streamlit" \
  "$HOME/Library/Python/3.10/bin/streamlit" \
  "$HOME/.local/bin/streamlit" \
  "/usr/local/bin/streamlit" \
  "/opt/homebrew/bin/streamlit"
do
  if [ -x "$candidate" ]; then
    STREAMLIT_BIN="$candidate"
    break
  fi
done

if [ -z "$STREAMLIT_BIN" ]; then
  STREAMLIT_BIN="$(command -v streamlit 2>/dev/null)"
fi

if [ -z "$STREAMLIT_BIN" ]; then
  echo "[launcher] FATAL: streamlit binary not found"
  osascript -e 'display alert "Analiza Kolarska" message "Nie znaleziono Streamlit. Zainstaluj zależności: pip install -r requirements lub pip install streamlit."' 2>/dev/null
  exit 1
fi
echo "[launcher] Using streamlit: $STREAMLIT_BIN"

# ---- Already running? just open the browser ----
if lsof -ti :"$PORT" >/dev/null 2>&1; then
  echo "[launcher] Port $PORT already in use — opening browser"
  open "$URL"
  exit 0
fi

# ---- Launch Streamlit ----
cd "$APP_DIR" || { echo "[launcher] FATAL: cannot cd to $APP_DIR"; exit 1; }
export PYTHONPATH="$APP_DIR:$PYTHONPATH"

nohup "$STREAMLIT_BIN" run app.py \
  --server.port "$PORT" \
  --server.headless true \
  --browser.gatherUsageStats false \
  > /tmp/analiza_kolarska_streamlit.log 2>&1 &
echo "[launcher] Started streamlit (PID=$!)"

# ---- Wait for server (up to 20s) ----
for i in $(seq 1 20); do
  sleep 1
  if curl -sf "$URL" >/dev/null 2>&1; then
    echo "[launcher] Server ready after ${i}s"
    break
  fi
done

open "$URL"
echo "[launcher] Browser opened at $URL"
