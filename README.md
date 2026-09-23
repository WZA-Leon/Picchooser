
<div align="center">
  <img src="https://raw.githubusercontent.com/WZA-Leon/Picchooser/main/icons/icon.png" alt="ICON" width="100%">
</div>


# Picchooser

一个基于 **EXIF 拍摄时间** 的照片自动整理工具。它会扫描指定目录下的图片，读取每张照片的拍摄时间，并按照拍摄间隔把照片自动归类为 **连拍**、**孤立的照片** 和 **无拍摄信息** 三类，帮你快速清理和归档照片。

## ✨ 功能特性

- 📂 **批量扫描**：自动扫描源目录下所有受支持的图片（默认 JPEG 系列）。
- ⏱️ **读取拍摄时间**：通过 [exifread](https://pypi.org/project/ExifRead/) 解析图片的 EXIF `DateTimeOriginal` 信息。
- 🔗 **连拍识别**：将拍摄时间间隔小于阈值（`burst_threshold`）的照片识别为一组连拍，归类到以 `burst_folder_prefix` 命名的文件夹中。
- 🖼️ **孤立照片识别**：与相邻照片时间间隔较大的单张照片，归类到 `single_folder_name` 文件夹。
- ❓ **无 EXIF 处理**：没有拍摄时间信息的图片，统一归入 `no_exif_folder_name` 文件夹。
- ⚙️ **配置驱动**：源目录、阈值、文件夹命名等全部通过 `photo_config.json` 配置，无需改代码。
- 🧭 **运行时可选择**：启动时在主菜单里选择以**复制**还是**移动**方式整理照片，还可直接**修改配置**或**切换目录**，一次分类结束后自动返回主菜单，无需重启。
- 🎨 **彩色控制台菜单**：主菜单、目录切换等界面用颜色区分不同类型项，一目了然。
- 🐍 **纯 Python 实现**：轻量、跨平台。

## 📁 项目结构

```
Picchooser/
├── Picchooser.py        # 主程序入口
├── photo_config.json    # 配置文件
├── pyproject.toml       # 项目与依赖声明（uv 管理）
├── Picchooser.spec      # PyInstaller 单文件打包配置
├── setup.iss            # Inno Setup 安装包脚本
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

该命令会按 `pyproject.toml` 创建 `.venv` 并安装运行依赖（`exifread`）与开发依赖（`pyinstaller`）。

> 不使用 uv 也可以：`pip install exifread`

#### 4. 配置

编辑项目根目录下的 `photo_config.json`：

```json
{
  "source_folder": ".",
  "dest_folder": null,
  "copy_mode": true,
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
| `copy_mode` | bool | 默认处理方式的建议值：`true` 复制原图（保留原图），`false` 移动原图。启动时仍会询问，回车即采用此默认值 |
| `burst_threshold` | int | 连拍判定阈值（秒）。两张照片拍摄间隔 ≤ 该值即视为同一组连拍 |
| `supported_ext` | array | 需要处理的图片扩展名列表 |
| `burst_folder_prefix` | string | 连拍文件夹的命名前缀 |
| `single_folder_name` | string | 孤立照片的文件夹名 |
| `no_exif_folder_name` | string | 无拍摄信息照片的文件夹名 |

#### 5. 运行

```bash
uv run python Picchooser.py
```

程序会读取 `photo_config.json`，先显示**主菜单**：

```
请选择处理方式：
  当前操作目录：E:\R6照片备份\100CANON
  [1] 复制原图（保留原图，占用额外磁盘空间）
  [2] 移动原图（不保留原图）
  [3] 修改配置
  [4] 切换目录
  [0] 退出
请输入 1 / 2 / 3 / 4 / 0（直接回车默认：复制）：
```

- **`1` 复制 / `2` 移动**：开始扫描源目录并完成分类整理；直接回车采用配置里的 `copy_mode` 默认值。
- **`3` 修改配置**：进入配置编辑菜单，逐项修改并自动写回 `photo_config.json`。
- **`4` 切换目录**：进入「选择文件夹」菜单，可直接把源目录切换到其它文件夹（选择结果会保存到配置）。
- **`0` 退出**：结束程序。

**一次分类完成后会暂停并自动返回主菜单**，可以继续对其它目录分类或修改配置，直到选择 `0` 退出。

#### 选择文件夹菜单

在主菜单选择 `4`（或在配置里切换 `source_folder`）时会进入「选择文件夹」菜单，可用数字序号进入子文件夹、返回上级或直接使用当前目录：

```
===== 选择文件夹 =====
  当前目录：E:\R6照片备份\100CANON
    [1] .. （返回上级目录）
  子文件夹：
    [2] 100CANON
    [3] 101CANON （无支持图片）
    [4] 使用当前目录
    [0] 取消
请选择要切换到的文件夹序号（0 取消）：
```

菜单用颜色区分不同类型的条目：

| 条目 | 颜色 | 说明 |
| --- | --- | --- |
| 当前目录 | 橙色 | 当前所在的目录路径 |
| 子文件夹（含支持图片） | 绿色 | 该文件夹（或其子目录）内存在受支持的图片 |
| 子文件夹（无支持图片） | 白色 | 该文件夹及其子目录内均无受支持的图片，会附带 `（无支持图片）` 标记 |
| 切换分区项 | 青色 | 到达磁盘根目录时列出其它分区（盘符）供切换 |

> 💡 选中「含支持图片」的目录后按回车即可切换；到达磁盘根目录时，`[1]` 位置会改为列出其它分区，方便跨盘切换。

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
4. 根据运行时选择的处理方式，把照片**复制**或**移动**到 `dest_folder`（或源目录下的分类文件夹）。

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
A：选择**复制**模式时原图不动，只是在分类文件夹里生成一份副本（会占用额外磁盘空间）；选择**移动**模式时原图会被移到分类文件夹，源目录不再保留，请谨慎使用。

**Q：复制和移动该怎么选？**
A：想保留原图、且磁盘空间充足时选**复制**；想直接整理归档、不保留原图时选**移动**。启动时按提示输入 `1`（复制）或 `2`（移动）即可，直接回车采用配置里的默认值。

**Q：分类完成后程序就退出了吗？**
A：不会。每次分类结束后会等待你按回车，然后**自动返回主菜单**，可以继续对其它目录分类、修改配置或切换目录，直到在主菜单输入 `0` 才退出。

**Q：怎么在不编辑 JSON 的情况下改配置 / 换目录？**
A：在主菜单选择 `3` 修改配置，会列出所有可编辑字段及当前值，按序号逐项修改并自动保存；选择 `4` 切换目录，则进入「选择文件夹」菜单选好目录，切换结果同样会写回 `photo_config.json`，下次启动自动生效。

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