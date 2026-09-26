// thumbnail.cpp
// 通过 Windows Shell 的 IShellItemImageFactory 接口获取文件缩略图。
//
// 导出 C 接口（供 Python ctypes 调用）：
//   int  thumb_get(const wchar_t* path, int size, unsigned char** out_pixels,
//                  int* out_width, int* out_height);
//   void thumb_free(unsigned char* pixels);
//
// 返回的像素为 BGRA 顺序（每像素 4 字节，自上而下），与 Windows 位图一致，
// 便于 Python 端直接转成 PIL Image 或 tkinter PhotoImage。
//
// 编译（MinGW g++）：
//   g++ -O2 -shared -o thumbnail.dll thumbnail.cpp \
//       -lole32 -loleaut32 -luuid -lgdi32 -static-libgcc -static-libstdc++
//
// 说明：
//   - 必须在调用线程初始化 COM（Python 端用 CoInitializeEx 完成）。
//   - 返回的缓冲区由本 DLL 用 malloc 分配，需调用 thumb_free 释放。

#include <windows.h>
#include <shobjidl.h>
#include <shlwapi.h>
#include <objbase.h>
#include <cstdlib>
#include <cstring>

// 导出宏：生成标准 C 符号，避免 C++ name mangling
#define THUMB_API extern "C" __declspec(dllexport)

// 把 HBITMAP 里的像素复制成自上而下的 BGRA 缓冲区
// 返回 malloc 分配的缓冲区；失败返回 nullptr
static unsigned char* copy_bitmap_to_bgra(HBITMAP hbmp, int width, int height) {
    if (!hbmp || width <= 0 || height <= 0) {
        return nullptr;
    }

    BITMAP bm = {};
    if (!GetObject(hbmp, sizeof(BITMAP), &bm)) {
        return nullptr;
    }

    // 用 32 位 DIB 承接 GetDIBits 的输出，保证每像素 4 字节 BGRA
    BITMAPINFO bmi = {};
    bmi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    bmi.bmiHeader.biWidth = width;
    // 负高度 = 自上而下，省去后续翻转
    bmi.bmiHeader.biHeight = -height;
    bmi.bmiHeader.biPlanes = 1;
    bmi.bmiHeader.biBitCount = 32;
    bmi.bmiHeader.biCompression = BI_RGB;

    const size_t stride = static_cast<size_t>(width) * 4;
    const size_t total = stride * static_cast<size_t>(height);
    unsigned char* buffer = static_cast<unsigned char*>(malloc(total));
    if (!buffer) {
        return nullptr;
    }

    HDC hdc = GetDC(nullptr);
    if (!hdc) {
        free(buffer);
        return nullptr;
    }

    int lines = GetDIBits(hdc, hbmp, 0, static_cast<UINT>(height),
                          buffer, &bmi, DIB_RGB_COLORS);
    ReleaseDC(nullptr, hdc);

    if (lines == 0) {
        free(buffer);
        return nullptr;
    }
    return buffer;
}

// 获取缩略图。
// path: 文件路径（宽字符）
// size: 期望的缩略图边长（像素），Shell 会按此尺寸返回
// out_pixels: 输出 BGRA 像素缓冲区指针（需 thumb_free 释放）
// out_width / out_height: 输出实际宽高
// 返回 0 成功，非 0 失败（HRESULT 或自定义错误码）
THUMB_API int thumb_get(const wchar_t* path, int size,
                        unsigned char** out_pixels,
                        int* out_width, int* out_height) {
    if (!path || !out_pixels || !out_width || !out_height) {
        return E_INVALIDARG;
    }
    *out_pixels = nullptr;
    *out_width = 0;
    *out_height = 0;

    IShellItemImageFactory* factory = nullptr;
    HRESULT hr = SHCreateItemFromParsingName(
        path, nullptr, IID_PPV_ARGS(&factory));
    if (FAILED(hr) || !factory) {
        return hr;
    }

    SIZE want = { size, size };
    // SIIGBF_BIGGERSIZEOK：允许返回比请求更大的图，避免放大失真
    // SIIGBF_THUMBNAILONLY：只取缩略图，不取图标
    HBITMAP hbmp = nullptr;
    hr = factory->GetImage(want, SIIGBF_BIGGERSIZEOK | SIIGBF_THUMBNAILONLY,
                           &hbmp);
    if (FAILED(hr) || !hbmp) {
        // 退一步：允许返回图标（某些格式没有缩略图）
        hr = factory->GetImage(want, SIIGBF_BIGGERSIZEOK, &hbmp);
    }
    factory->Release();

    if (FAILED(hr) || !hbmp) {
        return FAILED(hr) ? hr : E_FAIL;
    }

    // 用位图实际尺寸作为输出尺寸
    BITMAP bm = {};
    GetObject(hbmp, sizeof(BITMAP), &bm);
    int w = bm.bmWidth;
    int h = bm.bmHeight;

    unsigned char* pixels = copy_bitmap_to_bgra(hbmp, w, h);
    DeleteObject(hbmp);

    if (!pixels) {
        return E_OUTOFMEMORY;
    }

    *out_pixels = pixels;
    *out_width = w;
    *out_height = h;
    return 0;
}

// 释放 thumb_get 返回的像素缓冲区
THUMB_API void thumb_free(unsigned char* pixels) {
    if (pixels) {
        free(pixels);
    }
}

// DLL 入口（MinGW 下可选，保留以便将来扩展）
BOOL WINAPI DllMain(HINSTANCE, DWORD, LPVOID) {
    return TRUE;
}
