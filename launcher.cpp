#include <windows.h>
#include <filesystem>
#include <string>

namespace fs = std::filesystem;

int main()
{
    wchar_t szExePath[MAX_PATH] = { 0 };
    GetModuleFileNameW(NULL, szExePath, MAX_PATH);
    fs::path exePath(szExePath);
    fs::path appDir = exePath.parent_path();

    fs::path pythonExe = appDir / L"runtime" / L"pythonw.exe";
    fs::path ps1File = appDir / L"bootstrap_runtime.ps1";
    fs::path mainPy = appDir / L"Picchooser.py";

    if (!fs::exists(pythonExe))
    {
        std::wstring cmd = L"powershell.exe -ExecutionPolicy Bypass -File \"" + ps1File.wstring() + L"\"";

        STARTUPINFOW si = { sizeof(si) };
        PROCESS_INFORMATION pi;
        si.dwFlags = STARTF_USESHOWWINDOW;
        si.wShowWindow = SW_HIDE;

        if (!CreateProcessW(NULL, (LPWSTR)cmd.c_str(),
            NULL, NULL, FALSE, 0, NULL,
            appDir.c_str(), &si, &pi))
        {
            MessageBoxW(NULL, L"启动下载脚本失败", L"错误", MB_ICONERROR);
            return 1;
        }
        WaitForSingleObject(pi.hProcess, INFINITE);
        CloseHandle(pi.hThread);
        CloseHandle(pi.hProcess);

        if (!fs::exists(pythonExe))
        {
            MessageBoxW(NULL, L"运行环境下载失败！请检查网络", L"错误", MB_ICONERROR);
            return 1;
        }
    }

    std::wstring runCmd = L"\"" + pythonExe.wstring() + L"\" \"" + mainPy.wstring() + L"\"";
    STARTUPINFOW si2 = { sizeof(si2) };
    PROCESS_INFORMATION pi2;

    CreateProcessW(NULL, (LPWSTR)runCmd.c_str(),
        NULL, NULL, FALSE, 0, NULL,
        appDir.c_str(), &si2, &pi2);

    CloseHandle(pi2.hThread);
    CloseHandle(pi2.hProcess);

    return 0;
}
