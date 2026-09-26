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


