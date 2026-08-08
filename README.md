# C盘清理工具

Windows 11 C 盘清理 GUI 工具（Python 3.13 + tkinter，中文界面）。

## 功能

- **系统临时文件**：Temp、Prefetch 等
- **更新与旧系统残留**：Windows 更新缓存、Windows.old（默认不勾选，永久删除）
- **浏览器与诊断日志**：Chrome/Edge/Firefox 缓存、WER 报告、崩溃转储
- **已卸载软件残留**：扫描 Program Files 下疑似卸载残留的目录（高风险项移入回收站，可恢复）

## 安全设计

- 启动时自动请求管理员权限（拒绝则降级运行，仅可扫描）
- 单实例互斥锁，防止多实例同时删除
- 删除前五层校验：系统盘范围、清理项声明的前缀范围、系统关键目录黑名单、系统目录本体、运行中进程目录
- 目录统计跳过符号链接与 junction（防止 Windows 重解析环导致的扫描风暴）
- 已卸载软件残留检测遵循"宁漏勿误"：词元匹配已安装程序名、InstallLocation、运行中进程、近期文件活动、仅扫 Program Files

## 运行

```bash
pip install -r requirements.txt
python main.py
```

需要 Python 3.13+，仅支持 Windows。

## 打包为 exe

```bash
pip install pyinstaller
pyinstaller --noconsole --onefile --name "C盘清理工具" main.py
```

产物在 `dist/C盘清理工具.exe`（单文件，无需 Python 环境）。启动时应用内自动请求管理员权限，拒绝则降级运行（仅可扫描）。`C盘清理工具.spec` 为构建配置。

## 测试

```bash
python -m pytest
```

## 项目结构

```
core/       扫描、删除引擎、进程路径枚举、UAC 提权
cleaners/   四类清理器（含残留检测）
ui/         主窗口与后台线程
tests/      109+ 项测试
```
