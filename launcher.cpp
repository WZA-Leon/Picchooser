#include <windows.h>
#include <filesystem>
#include <string>

namespace fs = std::filesystem;

// 判断运行环境是否可用：python.exe 存在，且关键依赖（exifread / PIL）已安装
static bool IsRuntimeReady(const fs::path& runtimeDir)
{
    if (!fs::exists(runtimeDir / L"python.exe"))
        return false;
    if (!fs::exists(runtimeDir / L"Lib" / L"site-packages" / L"exifread"))
        return false;
    if (!fs::exists(runtimeDir / L"Lib" / L"site-packages" / L"PIL"))
        return false;
    return true;
}

int main()
{
    wchar_t szExePath[MAX_PATH] = { 0 };
    GetModuleFileNameW(NULL, szExePath, MAX_PATH);
    fs::path exePath(szExePath);
    fs::path appDir = exePath.parent_path();

    fs::path runtimeDir = appDir / L"runtime";
    fs::path pythonExe = runtimeDir / L"python.exe";
    fs::path ps1File = appDir / L"bootstrap_runtime.ps1";
    fs::path mainPy = appDir / L"Picchooser.py";

    // 环境不存在或损坏时，运行引导脚本安装
    if (!IsRuntimeReady(runtimeDir))
    {
        std::wstring cmd = L"powershell.exe -ExecutionPolicy Bypass -File \"" + ps1File.wstring() + L"\"";

        STARTUPINFOW si = { sizeof(si) };
        PROCESS_INFORMATION pi;
        si.dwFlags = STARTF_USESHOWWINDOW;
        si.wShowWindow = SW_SHOW;

        if (!CreateProcessW(NULL, &cmd[0],
            NULL, NULL, FALSE, 0, NULL,
            appDir.c_str(), &si, &pi))
        {
            MessageBoxW(NULL, L"启动下载脚本失败", L"错误", MB_ICONERROR);
            return 1;
        }
        WaitForSingleObject(pi.hProcess, INFINITE);
        CloseHandle(pi.hThread);
        CloseHandle(pi.hProcess);

        if (!IsRuntimeReady(runtimeDir))
        {
            MessageBoxW(NULL, L"运行环境安装失败！请检查网络", L"错误", MB_ICONERROR);
            return 1;
        }
    }

    // 设置 tkinter 所需的 Tcl/Tk 库路径（bootstrap 里设的不会传给本进程）
    SetEnvironmentVariableW(L"TCL_LIBRARY", (runtimeDir / L"tcl" / L"tcl8.6").c_str());
    SetEnvironmentVariableW(L"TK_LIBRARY", (runtimeDir / L"tcl" / L"k8.6").c_str());

    // 获取启动时的工作目录（CWD）。
    // - 在终端里输入 picc：CWD 是终端所在目录，应作为操作目录
    // - 双击 picc.exe：CWD 是程序安装目录，此时不传，让程序用配置里的上次目录
    wchar_t cwdBuf[MAX_PATH] = { 0 };
    DWORD cwdLen = GetCurrentDirectoryW(MAX_PATH, cwdBuf);
    fs::path startDir;
    if (cwdLen > 0 && cwdLen < MAX_PATH)
    {
        fs::path cwd(cwdBuf);
        std::error_code ec;
        fs::path cwdCanon = fs::weakly_canonical(cwd, ec);
        fs::path appCanon = fs::weakly_canonical(appDir, ec);
        if (cwdCanon != appCanon)
            startDir = cwd;  // 从其他目录调用，记录该目录
    }

    // 用 python.exe 启动命令行主程序，并分配独立控制台窗口
    std::wstring runCmd = L"\"" + pythonExe.wstring() + L"\" \"" + mainPy.wstring() + L"\"";
    STARTUPINFOW si2 = { sizeof(si2) };
    PROCESS_INFORMATION pi2;

    // 若从其他目录调用，则把该目录作为 python 的工作目录，并写入环境变量
    const wchar_t* workDir = startDir.empty() ? appDir.c_str() : startDir.c_str();
    if (!startDir.empty())
        SetEnvironmentVariableW(L"PICC_START_DIR", startDir.c_str());

    if (!CreateProcessW(NULL, &runCmd[0],
        NULL, NULL, FALSE, CREATE_NEW_CONSOLE, NULL,
        workDir, &si2, &pi2))
    {
        MessageBoxW(NULL, L"启动主程序失败", L"错误", MB_ICONERROR);
        return 1;
    }

    CloseHandle(pi2.hThread);
    CloseHandle(pi2.hProcess);

    return 0;
}
