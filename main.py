# -*- coding: utf-8 -*-
import socket
import threading
import time
import os
import configparser
import shutil
import subprocess


CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.ini")
cfg = configparser.ConfigParser()
cfg.read(CONFIG_FILE, encoding="utf-8")

SERVER_IP = cfg.get("server", "ip", fallback="bemfa.com")
SERVER_PORT = cfg.getint("server", "port", fallback=8344)
UID = cfg.get("auth", "uid")
TOPIC = cfg.get("topic", "name")
MAC_ADDR = cfg.get("device", "mac")
IP_ADDR = cfg.get("device", "ip")
USERNAME = cfg.get("device", "user")
PASSWORD = cfg.get("device", "password")

tcp_client_socket = None
socket_lock = threading.Lock()

# ---------------- 日志功能（带大小控制） ----------------
LOG_FILE = os.path.join(os.path.dirname(__file__), "wol.log")
MAX_LOG_SIZE = 5 * 1024 * 1024  # 最大 5MB

def log(msg):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)

    # 检查文件大小
    if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > MAX_LOG_SIZE:
        # 轮转方式：把旧日志重命名
        backup_file = LOG_FILE + ".bak"
        if os.path.exists(backup_file):
            os.remove(backup_file)
        os.rename(LOG_FILE, backup_file)

    # 写入日志
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ---------------- WOL 功能 ----------------
def wol(mac):
    mac_bytes = bytes.fromhex(mac.replace(":", "").replace("-", ""))
    magic = b"\xFF" * 6 + mac_bytes * 16

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.sendto(magic, ('255.255.255.255', 9))
    sock.close()
    log(f"[WOL] 已发送魔术包到 {mac}")

# ---------  ssh shutdown 功能 ------------
def shutdown_windows(ip, user,pwd):
    try:
        if shutil.which("sshpass") and pwd:
            cmd = [
                "sshpass", "-p", pwd, "ssh",
                "-o", "StrictHostKeyChecking=no",
                "-o", "PreferredAuthentications=password",
                f"{user}@{ip}",
                "shutdown /s /t 0"
            ]
        else:
            cmd = [
                "ssh",
                "-o", "StrictHostKeyChecking=no",
                f"{user}@{ip}",
                "shutdown /s /t 0"
            ]
        subprocess.run(cmd, timeout=5)
        print("[OK] Shutdown command sent.")
    except Exception as e:
        print("[ERR]", e)

# ------------- TCP 连接管理 --------------
def connect_server():
    """建立 TCP 连接（循环重试，不用递归）"""
    global tcp_client_socket

    while True:
        try:
            log("[NET] 正在连接服务器...")
            tcp_client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # tcp_client_socket.settimeout(30)

            tcp_client_socket.connect((SERVER_IP, SERVER_PORT))
            log("[NET] 连接成功！")

            # 订阅指令
            sub = f"cmd=1&uid={UID}&topic={TOPIC}\r\n"
            tcp_client_socket.send(sub.encode())
            log(f"[NET] 已订阅主题: {TOPIC}")
            return

        except Exception as e:
            log(f"[ERR] 连接失败，3 秒后重试: {e}")
            time.sleep(3)


# ------------------ 心跳线程 ------------------
def heartbeat_thread():
    """每 30 秒发送一次心跳（循环线程，不递归）"""
    global tcp_client_socket

    while True:
        time.sleep(30)
        try:
            with socket_lock:
                if tcp_client_socket:
                    tcp_client_socket.send(b"ping\r\n")
            log("[PING] 已发送心跳")

        except Exception as e:
            log(f"[ERR] 心跳失败: {e}")
            connect_server()  # 自动重连


# ------------------ 主接收线程 ------------------
def recv_thread():
    global tcp_client_socket

    while True:
        try:
            data = tcp_client_socket.recv(1024)

            # 服务器断开
            if not data:
                log("[ERR] 连接断开，重新连接...")
                connect_server()
                continue

            msg = data.decode("utf-8", errors="ignore").strip()
            log(f"[RECV] {msg}")

            # 触发 WOL
            if f"topic={TOPIC}&msg=on" in msg:
                log("[ACTION] 收到 WOL 指令，发送魔术包...")
                wol(MAC_ADDR)

            # 触发 远程关机
            if f"topic={TOPIC}&msg=off" in msg:
                log("[ACTION] 收到 远程关机 指令，建立SSH连接...")
                shutdown_windows(IP_ADDR, USERNAME, PASSWORD)

        except ConnectionResetError:
            log("[ERR] 连接被远端重置，重新连接...")
            connect_server()

        except ConnectionAbortedError:
            log("[ERR] 连接被中止，重新连接...")
            connect_server()

        except TimeoutError:
            log("[WARN] 接收超时，继续等待...")

        except OSError as e:
            log(f"[ERR] Socket 错误: {e}, 重新连接...")
            connect_server()

        except Exception as e:
            log(f"[ERR] 未知错误: {e}, 重新连接...")
            connect_server()

# --------------------- 主程序入口 ---------------------
if __name__ == "__main__":
    connect_server()

    # 启动心跳线程
    threading.Thread(target=heartbeat_thread, daemon=True).start()

    # 启动接收线程
    threading.Thread(target=recv_thread, daemon=True).start()

    # 主线程保持运行
    while True:
        time.sleep(1)