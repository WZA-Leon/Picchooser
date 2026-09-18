# Picchooser

一个基于 **EXIF 拍摄时间** 的照片自动整理工具。它会扫描指定目录下的图片，读取每张照片的拍摄时间，并按照拍摄间隔把照片自动归类为 **连拍**、**孤立的照片** 和 **无拍摄信息** 三类，帮你快速清理和归档照片。

## ✨ 功能特性

- 📂 **批量扫描**：自动扫描源目录下所有受支持的图片（默认 JPEG 系列）。
- ⏱️ **读取拍摄时间**：通过 [exifread](https://pypi.org/project/ExifRead/) 解析图片的 EXIF `DateTimeOriginal` 信息。
- 🔗 **连拍识别**：将拍摄时间间隔小于阈值（`burst_threshold`）的照片识别为一组连拍，归类到以 `burst_folder_prefix` 命名的文件夹中。
- 🖼️ **孤立照片识别**：与相邻照片时间间隔较大的单张照片，归类到 `single_folder_name` 文件夹。
- ❓ **无 EXIF 处理**：没有拍摄时间信息的图片，统一归入 `no_exif_folder_name` 文件夹。
- ⚙️ **配置驱动**：源目录、输出方式、阈值、文件夹命名等全部通过 `photo_config.json` 配置，无需改代码。
- 🔗 **硬链接整理**：默认以**硬链接**方式归类，原图保留且不重复占用磁盘空间；跨盘或文件系统不支持时自动退回复制。
- 🐍 **纯 Python 实现**：轻量、跨平台。

## 📁 项目结构

```
Picchooser/
├── Picchooser.py        # 主程序入口
├── photo_config.json    # 配置文件
├── pyproject.toml       # 项目与依赖声明（uv 管理）
├── Picchooser.spec      # PyInstaller 单文件打包配置
├── setup.iss            # Inno Setup 安装包脚本
├── tests/               # pytest 单元测试
│   ├── conftest.py      # 共享夹具（生成带 EXIF 的测试图片）
│   ├── test_config.py   # 配置加载
│   ├── test_exif.py     # EXIF 拍摄时间解析
│   ├── test_hardlink.py # 硬链接核心逻辑
│   ├── test_classify.py # 分类流程端到端
│   └── test_main.py     # 命令行入口
├── .gitignore           # Git 忽略规则
├── LICENSE              # 开源许可证
└── README.md            # 项目说明文档
```

## 🚀 快速开始

### 克隆源码

#### 1. 环境要求

- Python 3.8 或更高版本
- [uv](https://docs.astral.sh/uv/)（推荐，用于管理依赖与虚拟环境）

#### 2. 克隆项目

```bash
git clone https://github.com/WZA-Leon/Picchooser.git
cd Picchooser
```

#### 3. 安装依赖（uv）

```bash
uv sync
```

该命令会按 `pyproject.toml` 创建 `.venv` 并安装运行依赖（`exifread`）与开发依赖（`pytest` 等）。

> 不使用 uv 也可以：`pip install exifread`

#### 4. 配置

编辑项目根目录下的 `photo_config.json`：

```json
{
  "source_folder": ".",
  "dest_folder": null,
  "copy_mode": true,
  "fallback_copy": true,
  "burst_threshold": 3,
  "supported_ext": [".jpg", ".jpeg", ".JPG", ".JPEG"],
  "burst_folder_prefix": "连拍",
  "single_folder_name": "孤立的照片",
  "no_exif_folder_name": "无拍摄信息"
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `source_folder` | string | 待整理的源目录，默认为当前目录 `.` |
| `dest_folder` | string \| null | 整理后的输出目录；为 `null` 时在源目录内生成分类文件夹 |
| `copy_mode` | bool | `true` 硬链接（保留原图且不额外占用磁盘空间），`false` 移动原图 |
| `fallback_copy` | bool | 仅 `copy_mode` 为 `true` 时生效：硬链接不可用（跨盘、文件系统不支持等）时是否退回复制。`false` 则直接报错 |
| `burst_threshold` | int | 连拍判定阈值（秒）。两张照片拍摄间隔 ≤ 该值即视为同一组连拍 |
| `supported_ext` | array | 需要处理的图片扩展名列表 |
| `burst_folder_prefix` | string | 连拍文件夹的命名前缀 |
| `single_folder_name` | string | 孤立照片的文件夹名 |
| `no_exif_folder_name` | string | 无拍摄信息照片的文件夹名 |

#### 5. 运行

```bash
uv run python Picchooser.py
```

程序会读取 `photo_config.json`，扫描源目录并自动完成分类整理。

#### 6. 运行单元测试

本项目使用 **pytest** 编写单元测试，依赖已包含在开发依赖组中：

```bash
uv run pytest
```

常用参数：

```bash
uv run pytest -q                  # 精简输出
uv run pytest tests/test_hardlink.py   # 只跑硬链接相关测试
uv run pytest -k "burst"          # 按关键字筛选
```

测试覆盖：配置加载与默认值兜底、EXIF 拍摄时间解析、**硬链接核心逻辑**（建链、幂等、跨盘退回复制、删除链接不影响原图）、分类分组流程（连拍/孤立/无 EXIF、阈值边界、多次连拍编号）以及命令行入口。


### 自行打包为单文件 exe

项目使用 **PyInstaller**（已包含在开发依赖组，`uv sync` 会自动安装）打包为**单文件** exe，配置文件为 `Picchooser.spec`。

```bash
uv run pyinstaller Picchooser.spec --noconfirm --clean
```

产物：

```
dist/
└── picc.exe        # 单文件，约 8 MB，免安装、无需 Python 环境
```

把 `photo_config.json` 放在 **与 exe 相同的目录**（或运行时所在的当前目录）即可使用。

`Picchooser.spec` 中的几个关键设置：

| 设置 | 作用 |
| --- | --- |
| `EXE(... a.binaries, a.zipfiles, a.datas ...)` | 单文件模式：所有依赖都打进同一个 exe，运行时解压到临时目录 |
| `console=True` | 保留控制台窗口，便于看到分类日志输出 |
| `hiddenimports=["exifread"]` | 显式声明 `exifread`，避免动态导入被漏收 |
| `excludes=[...]` | 排除 `PIL`、`numpy`、`tkinter`、`pytest` 等本项目用不到的重型库，显著减小体积 |
| `upx=True` | 若系统装了 UPX 则自动压缩（未安装会跳过，不影响打包） |
| `icon=...` | 存在 `icon.ico` 时用作 exe 图标；不存在则自动跳过 |

> 💡 打包用的是 `Picchooser.spec` 而不是命令行参数，这样每次构建的配置都固定在版本库里，结果可复现。


### 直接获取 exe（免安装）

如果你不想安装 Python 环境，可以直接下载打包好的可执行文件（Windows）。

#### 1. 下载发布的最新版本

前往项目的 **Releases** 页面，下载最新的 `Picchooser.exe`：

👉 **https://github.com/WZA-Leon/Picchooser/releases/latest**

在 **Assets** 区域点击 `Picchooser.exe` 即可下载。

#### 2. 放置文件

将下载的 `Picchooser.exe` 放到任意目录，例如：

```
D:\Tools\Picchooser\Picchooser.exe
```

同时把 `photo_config.json` 放在 **与 exe 相同的目录**（或运行时所在的当前目录），程序会自动读取。

#### 3. 直接运行

在 exe 所在目录打开 PowerShell / CMD，运行：

```powershell
.\Picchooser.exe
```

#### 4. （可选）添加到环境变量 PATH，实现全局调用

配置好之后，就能在任意目录直接输入 `Picchooser` 运行，无需切换路径。

**图形界面方式（推荐）：**

1. 按 `Win` 键，搜索「**环境变量**」，点击「**编辑系统环境变量**」。
2. 点击「**环境变量(N)...**」按钮。
3. 在「**用户变量**」区域选中 `Path`，点击「**编辑(E)...**」。
4. 点击「**新建(N)**」，填入 `Picchooser.exe` 所在的**目录路径**（注意是目录，不是文件本身），例如：
   ```
   D:\Tools\Picchooser
   ```
5. 依次点击「**确定**」保存所有窗口。
6. **重新打开**一个新的 PowerShell / CMD 窗口（旧窗口不会生效）。

**命令行方式（PowerShell，追加到用户 PATH）：**

```powershell
[Environment]::SetEnvironmentVariable(
  "Path",
  [Environment]::GetEnvironmentVariable("Path", "User") + ";D:\Tools\Picchooser",
  "User"
)
```

> 请把 `D:\Tools\Picchooser` 换成你实际的 exe 目录。

#### 5. 验证是否配置成功

打开一个新的 PowerShell，输入：

```powershell
Picchooser
```

如果能正常运行，说明 PATH 配置成功。

> 💡 **提示**
> - 修改环境变量后必须**新开终端窗口**才生效。
> - 如果提示「无法将"Picchooser"项识别为 cmdlet」，通常是路径填错（填了文件而非目录）或没有重开终端。
> - 首次运行若被 Windows SmartScreen 拦截，点击「更多信息」→「仍要运行」即可。



## 🛠️ 工作原理

1. 遍历 `source_folder` 中所有扩展名在 `supported_ext` 内的图片。
2. 读取每张图片的 EXIF 拍摄时间 `DateTimeOriginal`：
   - 读取失败的图片 → 归入 `no_exif_folder_name`。
   - 读取成功的图片 → 按拍摄时间排序。
3. 比较相邻照片的拍摄间隔：
   - 间隔 ≤ `burst_threshold` 秒 → 判定为 **连拍**，归入 `burst_folder_prefix` 命名的文件夹。
   - 间隔较大、孤立出现 → 归入 `single_folder_name`。
4. 根据 `copy_mode` 决定是建立硬链接还是移动原图到 `dest_folder`（或源目录下的分类文件夹）。

## 📝 示例

假设 `burst_threshold` 为 `3`，源目录中有 5 张照片：

| 文件名 | 拍摄时间 | 归类结果 |
| --- | --- | --- |
| IMG_001.jpg | 10:00:00 | 连拍 |
| IMG_002.jpg | 10:00:01 | 连拍 |
| IMG_003.jpg | 10:00:02 | 连拍 |
| IMG_004.jpg | 15:30:00 | 孤立的照片 |
| IMG_005.jpg | ——（无 EXIF） | 无拍摄信息 |

整理后目录结构：

```
连拍/
├── IMG_001.jpg
├── IMG_002.jpg
└── IMG_003.jpg
孤立的照片/
└── IMG_004.jpg
无拍摄信息/
└── IMG_005.jpg
```

## ❓ 常见问题

**Q：为什么有些照片被判为「无拍摄信息」？**
A：图片缺少 EXIF 数据（如经过压缩、截图、社交软件转发），或 EXIF 中没有 `DateTimeOriginal` 字段。

**Q：`burst_threshold` 设多少合适？**
A：连拍通常是每秒数张，建议设为 `1~3` 秒；若想更宽松地合并相册，可适当调大。

**Q：会修改我的原始照片吗？**
A：`copy_mode` 为 `true` 时只建立**硬链接**，原图不动，而且分类结果不会重复占用磁盘空间；设为 `false` 时才会移动原图，请谨慎使用。

**Q：硬链接和复制有什么区别？**
A：硬链接让分类文件夹里的文件和原图指向**同一份数据**（同一个文件），因此：
- 不会额外占用磁盘空间，整理大量照片时尤其明显；
- 修改其中任意一处内容，另一处同步变化（例如用修图软件直接覆盖保存原图，需留意）；
- **删除**其中一处不会影响另一处，只有全部链接都删除后数据才真正释放；
- 硬链接不能跨磁盘分区，所以 `dest_folder` 若在另一个盘，会自动退回复制（由 `fallback_copy` 控制）。

**Q：`fallback_copy` 设成 `false` 会怎样？**
A：硬链接失败时程序会直接报错退出，而不是悄悄退回复制。适合你希望「要么硬链接、要么别动」的场景。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 新建分支：`git checkout -b feature/your-feature`
3. 提交改动：`git commit -m "Add some feature"`
4. 推送分支：`git push origin feature/your-feature`
5. 提交 Pull Request

## 📄 许可证

本项目基于 [MIT License](LICENSE) 开源。

## 👤 作者

**WZA-Leon**

- GitHub: [@WZA-Leon](https://github.com/WZA-Leon)