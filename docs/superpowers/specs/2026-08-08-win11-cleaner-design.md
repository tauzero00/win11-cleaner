# Windows 11 C 盘清理工具 — 设计文档

日期：2026-08-08
状态：已批准（用户逐节确认）

## 目标

一个 Windows 11 上的 C 盘清理 GUI 工具，扫描各类垃圾文件 → 用户勾选 → 确认后清理，释放磁盘空间。

## 技术栈与形态

- Python 3 + tkinter 图形界面，界面语言为中文
- 依赖：`send2trash`（移入回收站）
- 启动时自动请求管理员权限（UAC）
- 单实例运行（命名互斥锁，防止两个实例同时清理）

## 清理流程

扫描 → 左侧勾选类别（全选该类） → 右侧可单独取消个别文件 → 底部实时显示已选大小 → 点「开始清理」→ 确认对话框 → 后台删除 → 结果汇总。

## 架构

模块化清理器架构。每个清理类别是一个独立 `Cleaner` 类，统一接口：

- `CleanItem`：路径、所属 Cleaner、大小、文件数、风险等级、是否勾选
- `Cleaner.scan() -> list[CleanItem]`：返回该类的所有可清理项
- `Cleaner.clean(items)`：删除指定项

### 目录结构

```
win11-cleaner/
├── main.py              # 入口：UAC 提权 + 启动 tkinter 应用
├── cleaners/
│   ├── __init__.py      # 注册所有 Cleaner
│   ├── base.py          # Cleaner 抽象基类 + CleanItem 数据模型
│   ├── temp_files.py    # 系统临时文件（%TEMP%、C:\Windows\Temp、缩略图缓存、Prefetch）
│   ├── update_cache.py  # 更新缓存（SoftwareDistribution、传递优化、Windows.old）
│   ├── browser_logs.py  # 浏览器缓存（Chrome/Edge/Firefox）+ 诊断日志（WER、崩溃转储）
│   └── orphan_remnants.py # 已卸载软件残留（孤儿目录检测）
├── core/
│   ├── deleter.py       # 删除引擎：永久删除 / 移入回收站（send2trash）
│   ├── scanner.py       # 后台扫描线程 + 目录大小计算
│   └── elevation.py     # UAC 自动提权（ShellExecute runas）+ 单实例锁
├── ui/
│   ├── app.py           # 主窗口
│   └── threads.py       # 扫描/清理后台线程与 UI 回调桥接
└── requirements.txt     # send2trash
```

## 界面设计

主窗口 900×600。左侧清理类别列表（勾选框 + 各类总大小），右侧扫描结果列表（勾选框 + 路径 + 大小，按大小排序），底部已选大小汇总与「开始清理」按钮，进度条显示扫描/清理进度。

## 线程模型

- tkinter 主线程只负责界面与勾选收集
- 后台线程负责扫描（遍历目录计算大小）与清理（逐个删除）
- 后台线程通过 `queue` 发进度消息，主线程用 `after()` 轮询刷新，不在子线程操作 tkinter 控件

## 清理类别与删除策略

| 类别 | 清理内容 | 风险 | 删除方式 |
|---|---|---|---|
| 系统临时文件 | `%TEMP%`、`C:\Windows\Temp`、缩略图缓存、Prefetch | 低 | 永久删除 |
| 更新与旧系统残留 | `SoftwareDistribution\Download`、传递优化缓存、`Windows.old` | 中-高 | 永久删除；Windows.old 单独标注体积并需明确确认 |
| 浏览器与诊断日志 | Chrome/Edge/Firefox 缓存、WER 错误报告（`C:\ProgramData\Microsoft\Windows\WER`）、崩溃转储（`%LOCALAPPDATA%\CrashDumps`） | 低 | 永久删除 |
| 已卸载软件残留 | Program Files / ProgramData / AppData 中的孤儿目录 | 高 | 默认移入回收站，可切换永久删除，逐项确认 |

### 软件残留检测（启发式）

1. 枚举 `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall` 及 WOW6432Node，得到已安装程序名集合
2. 枚举 `Program Files`、`Program Files (x86)`、`ProgramData`、`%LOCALAPPDATA%`、`%APPDATA%` 第一级目录
3. 目录名与已安装程序名模糊匹配，对不上的列为"疑似残留"候选
4. 内置排除白名单（VCRuntime、DirectX、Common Files、Windows Kits 等系统目录），避免误报

## 安全边界

- 永不删除：正在使用的文件（失败自动跳过计入结果）、系统关键目录、白名单目录
- 删除前所有项在界面上可见、可取消勾选
- 扫描阶段只计算大小，不删除任何文件

## 错误处理

- 权限拒绝（AccessDenied）：扫描时跳过计入"不可访问"；清理时跳过并标记失败
- 文件占用：清理时重试 2 次（间隔 1 秒），仍失败标记失败并继续
- 目录不存在：静默跳过
- 删除引擎：`shutil.rmtree`（永久）与 `send2trash`（回收站），失败返回原因展示在结果对话框
- 提权失败（拒绝 UAC）：提示后降级为普通权限模式运行，可清理的类别照常工作
- 单实例锁：命名互斥锁防并发

## 测试策略

- 单元测试（pytest）：
  - 各 Cleaner 的 scan 逻辑：用 `tmp_path` 构造假垃圾文件，验证大小计算与文件数
  - 删除引擎：永久/回收站删除的成功、失败、占用重试路径
  - 残留检测：构造假"已安装程序"数据 + 假目录，验证匹配/白名单/模糊匹配
- 测试不触碰真实系统目录，全部隔离在临时目录
- 手工验证清单：在真实 Windows 11 上验证提权、扫描速度、清理结果

## 验收标准

1. 启动自动提权，UAC 拒绝时降级运行
2. 四类清理项都能正确扫描出大小与文件数
3. 勾选、清理流程顺畅，清理后大小与预期一致
4. 软件残留检测不误报系统目录
5. 文件占用时不崩溃，失败项在结果中报告
