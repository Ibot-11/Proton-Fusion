/* SPDX-License-Identifier: MIT */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>

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
    WCHAR setting[2];
    BOOL alpha = GetEnvironmentVariableW(L"FUSION_PAINT_PROBE_ALPHA", setting, 2) != 0;
    BOOL black = GetEnvironmentVariableW(L"FUSION_PAINT_PROBE_BLACK", setting, 2) != 0;
    BOOL unaware = GetEnvironmentVariableW(L"FUSION_PAINT_PROBE_UNAWARE", setting, 2) != 0;
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
    ShowWindow(panel, SW_SHOWNOACTIVATE);
    if (alpha) {
        SetWindowLongPtrW(panel, GWL_EXSTYLE, GetWindowLongPtrW(panel, GWL_EXSTYLE)|WS_EX_LAYERED);
        SetLayeredWindowAttributes(panel, 0, 128, LWA_ALPHA);
    }
    pump(250);
    /* Change geometry within the buffered surface before the first drawing. */
    SetWindowPos(panel, NULL, 900, 250, MulDiv(380,dpi,96), MulDiv(alpha ? 610 : 360,dpi,96), SWP_NOACTIVATE|SWP_NOZORDER);
    pump(250);
    dc = GetDC(panel);
    brush = CreateSolidBrush(black ? RGB(0,0,0) : RGB(51,119,187));
    GetClientRect(panel, &rect);
    FillRect(dc, &rect, brush);
    ReleaseDC(panel, dc);
    DeleteObject(brush);
    SetWindowTextW(panel, L"FusionPaintProbe-Painted");
    pump(600);
    DestroyWindow(panel);
    DestroyWindow(owner);
    ExitProcess(0);
}
