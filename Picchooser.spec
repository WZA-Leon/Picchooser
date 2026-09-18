# -*- mode: python ; coding: utf-8 -*-
r"""PyInstaller 打包配置：单文件（onefile）模式。

打包命令：
    uv run pyinstaller Picchooser.spec

产物：dist\picc.exe（单文件，免安装）
"""

import os

block_cipher = None

# 图标可选：存在才使用，避免没有 icon.ico 时打包报错
icon_file = "icon.ico"
icon_arg = icon_file if os.path.exists(icon_file) else None

a = Analysis(
    ["Picchooser.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=["exifread"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 体积优化：排除本项目用不到的重型库，显著减小单文件体积
    excludes=[
        "tkinter",
        "unittest",
        "pydoc",
        "doctest",
        "test",
        "pytest",
        "piexif",
        "PIL",
        "numpy",
        "matplotlib",
        "setuptools",
        "pip",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="picc",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,          # 命令行程序，保留控制台输出
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_arg,
)