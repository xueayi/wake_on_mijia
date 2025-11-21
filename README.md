# Wake On Mijia (wom)

通过订阅巴法云主题并接收控制消息，在本地网络广播 WOL 魔术包以唤醒指定设备，并支持ssh实现Windows远程关机。项目提供 systemd 与 SysV init 两种安装方式，支持自动重连、心跳与日志轮转，适合守护进程部署。

## 功能特性

- 连接 `bemfa.com` 并订阅指定主题，收到 `on` 指令后发送 WOL 魔术包
- 自动重连与心跳维持（30 秒 `ping`），健壮性更好
- 日志写入 `wol.log` 并进行 5MB 大小轮转
- 支持 systemd 与 SysV init 安装，安装脚本自动判断环境
- `config.ini` 管理用户参数，无需改动代码
- 基于Windows OpenSSH Server的远程关机

## 目录结构

- `main.py`：守护进程入口，网络连接与 WOL 逻辑
- `config.ini`：用户参数配置（服务器、UID、主题、MAC）
- `install.sh`：安装脚本，自动选择 systemd 或 init，并提示输入 `main.py` 路径

## 快速开始

1. 准备环境
   - 具有 `python3` 的 Linux 主机
   - Linux 主机可访问外网网络（连接 `bemfa.com:8344`）
   - 目标控制的电脑设备网卡支持 WOL
2. 在巴法云平台创建主题
3. 配置参数
   - 编辑 `config.ini`：

     ```ini
     [server]
     ip=bemfa.com
     port=8344

     [auth]
     uid=<巴法云分配给你的私钥>

     [topic]
     name=<在巴法云中添加的主题>

     [device]
     mac=<你的设备MAC，如 CC:28:AA:04:00:53>
     ```

   - 其中uid为巴法云分配给你的私钥
   - name是巴法云创建的TCP设备云的主题名称（以三位数字006结尾，006代表开关类型）

4. 远程关机配置（如不需要设置关机可以跳过）

   - 在 Windows 启用 OpenSSH Server，使 Linux 主机可通过 SSH 执行关机命令。
   - 进入 “设置 → 系统 → 可选功能 → 添加功能”，安装 **OpenSSH Server**。
   - 管理员 PowerShell 启动并设置自启：

   ```powershell
   Start-Service sshd
   Set-Service sshd -StartupType Automatic
   ```

   - 放行防火墙端口：

   ```powershell
   New-NetFirewallRule -Name sshd -Protocol TCP -LocalPort 22 -Action Allow
   ```

   - 在powershell中用`whoami`可以查看自己的用户名
   - 在 `C:\Users\<User>\` 下创建 `.ssh` 目录与 `authorized_keys` 文件，并设置权限，`<User>`手动替换成自己的用户名：

   ```powershell
   icacls "C:\Users\<User>\.ssh" /inheritance:r
   icacls "C:\Users\<User>\.ssh" /grant <User>:F
   icacls "C:\Users\<User>\.ssh\authorized_keys" /inheritance:r
   icacls "C:\Users\<User>\.ssh\authorized_keys" /grant <User>:F
   ```

   - 生成 SSH 密钥并通过ssh复制到Windows用户目录下，手动将 `~/.ssh/id_rsa.pub` 内容添加到 Windows 的 `authorized_keys` 中：

   ```bash
   ssh-keygen
   ssh-copy-id user@windows_ip
   ```

   - 测试连接

   ```bash
   ssh -o StrictHostKeyChecking=no user@windows_ip
   ```

5. 在Linux主机安装本服务
   - 执行：`sudo bash install.sh`或者`./install.sh`
   - 按提示输入 `main.py` 的绝对路径，例如：`/root/bemfa/wol/main.py`
   - 脚本将自动：
     - 若支持 systemd：生成并安装 `wom.service`，启用并启动
     - 若不支持 systemd：生成 `/etc/init.d/wom`，注册并启动

6. 验证运行
   - systemd：
     - 查看状态：`sudo systemctl status wom`
     - 查看日志：`journalctl -u wom -f`
   - init：
     - 查看状态：`/etc/init.d/wom status`
     - 日志：`/var/log/wom.log`

7. 在第三方平台添加
   - 米家app：
     - 在米家app中绑定巴法云平台
     - 如果有小爱音箱可以创建小爱音箱的"自定义指令"，从而添加到米家“自动化”任务触发
     - 如果没有小爱音箱，直接使用小爱同学命令控制，区别是不能添加到米家“自动化”
   - home assistant
   - 其他支持连接巴法云的平台

## 配置说明

- `server.ip` / `server.port`：巴法云服务器地址与端口
- `auth.uid`：你的 UID，请替换为自己的值
- `topic.name`：订阅主题名，控制消息形如 `topic=<name>&msg=on`
- `device.mac`：被唤醒设备的 MAC 地址，支持 `AA:BB:CC:DD:EE:FF`

## 服务管理

- systemd
  - 启动：`sudo systemctl start wom`
  - 重启：`sudo systemctl restart wom`
  - 开机自启：`sudo systemctl enable wom`
  - 停止：`sudo systemctl stop wom`
  - 日志：`journalctl -u wom -f`
- init
  - 启动：`/etc/init.d/wom start`
  - 重启：`/etc/init.d/wom restart`
  - 停止：`/etc/init.d/wom stop`
  - 开机自启：`/etc/init.d/bemfa_wol enable`

## 日志与排错

- 业务日志：`wol.log`（与 `main.py` 同目录），超过 5MB 轮转到 `wol.log.bak`
- systemd：使用 `journal`，查看 `journalctl -u wom -f`
- init：标准输出/错误重定向至 `/var/log/wom.log`
- 常见问题：
  - 无法连接服务器：检查防火墙与 DNS，确认 `bemfa.com:8344` 可达
  - 收到指令但未唤醒：
    - 检查目标主机 BIOS/操作系统是否启用 WOL
    - 局域网是否允许广播，端口 `9` 是否被阻断
    - MAC 地址是否正确，交换机/AP 是否隔离广播
  - 网络未就绪导致启动失败：systemd 单元使用 `network-online.target`，确保网络服务可用

## 运行与开发

- 手动运行（调试）：
  - `cd <main.py所在目录>`
  - `python3 main.py`
- 修改配置无需改代码，直接编辑 `config.ini`

## 卸载

- systemd：
  - `sudo systemctl stop wom && sudo systemctl disable wom`
  - 删除单元文件：`sudo rm /etc/systemd/system/wom.service && sudo systemctl daemon-reload`
- init：
  - 停止并删除脚本：`/etc/init.d/wom stop && sudo rm /etc/init.d/wom`

## 安全建议

- 不要在公共仓库中提交真实 UID
- 如需非 `root` 运行，请为运行用户配置访问日志/工作目录权限
