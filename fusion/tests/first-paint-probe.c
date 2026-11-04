/* SPDX-License-Identifier: MIT */
#define WIN32_LEAN_AND_MEAN
#define COBJMACROS
#include <windows.h>
#include <d3d11.h>
#include <dxgi.h>

static IDXGISwapChain *swapchain;
static ID3D11Device *device;
static ID3D11DeviceContext *context;

static void gpu_create(HWND panel)
{
    static DXGI_SWAP_CHAIN_DESC desc;
    D3D_FEATURE_LEVEL level;
    desc.BufferDesc.Format = DXGI_FORMAT_B8G8R8A8_UNORM;
    desc.SampleDesc.Count = 1;
    desc.BufferUsage = DXGI_USAGE_RENDER_TARGET_OUTPUT;
    desc.BufferCount = 2;
    desc.OutputWindow = panel;
    desc.Windowed = TRUE;
    desc.SwapEffect = DXGI_SWAP_EFFECT_DISCARD;
    if (FAILED(D3D11CreateDeviceAndSwapChain(NULL, D3D_DRIVER_TYPE_HARDWARE, NULL, 0,
        NULL, 0, D3D11_SDK_VERSION, &desc, &swapchain, &device, &level, &context))) ExitProcess(31);
}

static void gpu_paint(void)
{
    static const float color[4] = {0.2f, 119.0f / 255.0f, 187.0f / 255.0f, 1};
    ID3D11Texture2D *buffer;
    ID3D11RenderTargetView *view;
    static const GUID texture_iid = {0x6f15aaf2, 0xd208, 0x4e89, {0x9a,0xb4,0x48,0x95,0x35,0xd3,0x4f,0x9c}};
    if (FAILED(IDXGISwapChain_GetBuffer(swapchain, 0, &texture_iid, (void **)&buffer))) ExitProcess(32);
    if (FAILED(ID3D11Device_CreateRenderTargetView(device, (ID3D11Resource *)buffer, NULL, &view))) ExitProcess(33);
    ID3D11DeviceContext_ClearRenderTargetView(context, view, color);
    ID3D11DeviceContext_Flush(context);
    if (FAILED(IDXGISwapChain_Present(swapchain, 0, 0))) ExitProcess(34);
    ID3D11RenderTargetView_Release(view);
    ID3D11Texture2D_Release(buffer);
}

static LRESULT CALLBACK proc(HWND w, UINT m, WPARAM p, LPARAM l)
{
    if (m == WM_ERASEBKGND) return 1;
    if (m == WM_PAINT) { ValidateRect(w, NULL); return 0; }
    return DefWindowProcW(w, m, p, l);
}

static void pump(DWORD duration)
{
    DWORD end = GetTickCount() + duration;
    MSG m;
    while ((int)(end - GetTickCount()) > 0) {
        while (PeekMessageW(&m, NULL, 0, 0, PM_REMOVE)) { TranslateMessage(&m); DispatchMessageW(&m); }
        MsgWaitForMultipleObjects(0, NULL, FALSE, 5, QS_ALLINPUT);
    }
}

void WINAPI WinMainCRTStartup(void)
{
    WNDCLASSW wc = {0};
    HWND owner, panel;
    RECT rect;
    HDC dc;
    HBRUSH brush;
    UINT dpi;
    WCHAR setting[8], gpu_mode[8];
    BOOL alpha = GetEnvironmentVariableW(L"FUSION_PAINT_PROBE_ALPHA", setting, 2) != 0;
    BOOL black = GetEnvironmentVariableW(L"FUSION_PAINT_PROBE_BLACK", setting, 2) != 0;
    BOOL unaware = GetEnvironmentVariableW(L"FUSION_PAINT_PROBE_UNAWARE", setting, 2) != 0;
    BOOL gpu = GetEnvironmentVariableW(L"FUSION_PAINT_PROBE_GPU", gpu_mode, 8) != 0;
    BOOL gpu_before_show = gpu && gpu_mode[0] == 'b';
    SetProcessDpiAwarenessContext(unaware ? DPI_AWARENESS_CONTEXT_UNAWARE : DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
    wc.lpfnWndProc = proc;
    wc.hInstance = GetModuleHandleW(NULL);
    wc.lpszClassName = L"FusionFirstPaintOwner";
    RegisterClassW(&wc);
    owner = CreateWindowW(wc.lpszClassName, L"FusionPaintProbe-Owner", WS_OVERLAPPEDWINDOW,
                          100, 100, 1200, 900, NULL, NULL, wc.hInstance, NULL);
    ShowWindow(owner, SW_SHOWNOACTIVATE);
    pump(200);
    dpi = GetDpiForWindow(owner);
    if (!dpi) dpi = 96;
    wc.lpszClassName = L"Qt683QWindowToolSaveBits";
    RegisterClassW(&wc);
    panel = CreateWindowExW(WS_EX_TOOLWINDOW, wc.lpszClassName, L"FusionPaintProbe-Waiting",
                            WS_POPUP, 500, 400, MulDiv(370,dpi,96), MulDiv(alpha ? 600 : 345,dpi,96),
                            owner, NULL, wc.hInstance, NULL);
    if (gpu_before_show) gpu_create(panel);
    ShowWindow(panel, SW_SHOWNOACTIVATE);
    if (alpha) {
        SetWindowLongPtrW(panel, GWL_EXSTYLE, GetWindowLongPtrW(panel, GWL_EXSTYLE)|WS_EX_LAYERED);
        SetLayeredWindowAttributes(panel, 0, 128, LWA_ALPHA);
    }
    pump(250);
    /* Change geometry within the buffered surface before the first drawing. */
    SetWindowPos(panel, NULL, 900, 250, MulDiv(380,dpi,96), MulDiv(alpha ? 610 : 360,dpi,96), SWP_NOACTIVATE|SWP_NOZORDER);
    pump(250);
    if (gpu) {
        SetWindowTextW(panel, L"FusionPaintProbe-Switching");
        if (!gpu_before_show) gpu_create(panel);
        gpu_paint();
    } else {
        dc = GetDC(panel);
        brush = CreateSolidBrush(black ? RGB(0,0,0) : RGB(51,119,187));
        GetClientRect(panel, &rect);
        FillRect(dc, &rect, brush);
        ReleaseDC(panel, dc);
        DeleteObject(brush);
    }
    SetWindowTextW(panel, L"FusionPaintProbe-Painted");
    pump(600);
    if (gpu) {
        IDXGISwapChain_Release(swapchain);
        ID3D11DeviceContext_ClearState(context);
        ID3D11DeviceContext_Release(context);
        ID3D11Device_Release(device);
    }
    DestroyWindow(panel);
    DestroyWindow(owner);
    ExitProcess(0);
}
