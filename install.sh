#!/bin/bash
set -e

echo "请选择 main.py 路径："
echo "  1) 使用当前目录下的 main.py"
echo "  2) 手动输入 main.py 的绝对路径"
read -p "请输入选项 [1/2]: " CHOICE

if [ "$CHOICE" = "1" ]; then
  MAIN_PY="$(pwd)/main.py"
  echo "使用当前目录: $MAIN_PY"
elif [ "$CHOICE" = "2" ]; then
  read -p "请输入 main.py 的绝对路径: " MAIN_PY
else
  echo "无效选项"
  exit 1
fi

if [ -z "$MAIN_PY" ] || [ ! -f "$MAIN_PY" ]; then
  echo "路径无效: $MAIN_PY"
  exit 1
fi

PYTHON3=$(command -v python3 || echo /usr/bin/python3)
if [ ! -x "$PYTHON3" ]; then
  echo "未找到 python3"
  exit 1
fi

WORKDIR=$(cd "$(dirname "$MAIN_PY")" && pwd)

if command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; then
  UNIT_PATH=/etc/systemd/system/wom.service
  cat > "$UNIT_PATH" <<EOF
[Unit]
Description=Wake On Mijia daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$WORKDIR
ExecStart=$PYTHON3 $MAIN_PY
Restart=always
RestartSec=3
User=root
Environment=PYTHONUNBUFFERED=1
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable wom
  systemctl restart wom
  echo "已使用 systemctl 安装并启动 wom"
else
  INIT_PATH=/etc/init.d/wom
  cat > "$INIT_PATH" <<'EOF'
#!/bin/sh /etc/rc.common
START=95
STOP=10
USE_PROCD=1
NAME="wom"
PIDFILE="/var/run/wom.pid"
DAEMON="%PYTHON3%"
DAEMON_OPTS="%MAIN_PY%"
WORKDIR="%WORKDIR%"

start_service() {
    procd_open_instance
    procd_set_param command "$DAEMON" "$DAEMON_OPTS"
    procd_set_param respawn  5 5 5
    procd_set_param stdout 1
    procd_set_param stderr 1
    procd_set_param pidfile "/var/run/$NAME.pid"
    procd_set_param directory "$WORKDIR"
    procd_close_instance
}
EOF
  sed -i "s|%PYTHON3%|$PYTHON3|g" "$INIT_PATH"
  sed -i "s|%MAIN_PY%|$MAIN_PY|g" "$INIT_PATH"
  sed -i "s|%WORKDIR%|$WORKDIR|g" "$INIT_PATH"
  chmod +x "$INIT_PATH"
  if command -v update-rc.d >/dev/null 2>&1; then
    update-rc.d wom defaults
  elif command -v chkconfig >/dev/null 2>&1; then
    chkconfig --add wom || true
    chkconfig wom on || true
  fi
  "$INIT_PATH" restart
  echo "已使用 init 安装并启动 wom"
  ps | grep wom
  "$INIT_PATH" status
fi