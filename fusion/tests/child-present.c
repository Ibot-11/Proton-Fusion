/* Repro for the stale-frame (snap) bug: D3D11 swapchain on a WS_CHILD window.
 * Each burst presents 1-4 frames, then the app goes idle (like Fusion between
 * mouse events). After the last Present of a burst a line is appended to the
 * log so an external checker can compare the real X11 window content.
 *
 * child-present.exe <logfile> <bursts> <effect> <stress frames> <gpu copies>
 *                   <cpu ms> <size> <resize> <minimize>
 * Derived from the project's local D3D11 child-window investigation.
 * SPDX-License-Identifier: MIT
 */
#define WIN32_LEAN_AND_MEAN
#define COBJMACROS
#define INITGUID
#include <windows.h>
#include <d3d11.h>
#include <dxgi.h>

void *memset(void *d, int c, size_t n)
{
    void *r = d;
    __asm__ volatile("rep stosb" : "+D"(d), "+c"(n) : "a"(c) : "memory");
    return r;
}

static const float palette[8][4] = {
    {1, 0, 0, 1}, {0, 1, 0, 1}, {0, 0, 1, 1}, {1, 1, 0, 1},
    {0, 1, 1, 1}, {1, 0, 1, 1}, {1, 1, 1, 1}, {1, 0.5f, 0, 1},
};

static HANDLE logfile;
static unsigned rng = 12345;
static unsigned rnd(void) { rng = rng * 1664525u + 1013904223u; return rng >> 8; }

static void argument(WCHAR **command, WCHAR *value, unsigned capacity)
{
    WCHAR *p = *command;
    unsigned i = 0;
    int quoted = 0;
    while (*p == ' ') p++;
    if (*p == '"') { quoted = 1; p++; }
    while (*p && (quoted ? *p != '"' : *p != ' ')) {
        if (i + 1 < capacity) value[i++] = *p;
        p++;
    }
    value[i] = 0;
    if (quoted && *p == '"') p++;
    *command = p;
}

static int number(WCHAR **command, int fallback)
{
    WCHAR value[32];
    int i, result = 0;
    argument(command, value, 32);
    if (!value[0]) return fallback;
    for (i = 0; value[i]; i++) {
        if (value[i] < '0' || value[i] > '9') return fallback;
        result = result * 10 + value[i] - '0';
    }
    return result;
}

static LRESULT CALLBACK wndproc(HWND w, UINT m, WPARAM wp, LPARAM lp)
{
    if (m == WM_ERASEBKGND) return 1;
    if (m == WM_DESTROY) { PostQuitMessage(0); return 0; }
    return DefWindowProcW(w, m, wp, lp);
}

static BOOL pump(DWORD ms)
{
    DWORD end = GetTickCount() + ms;
    MSG msg;
    for (;;) {
        while (PeekMessageW(&msg, NULL, 0, 0, PM_REMOVE)) {
            if (msg.message == WM_QUIT) return FALSE;
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
        if ((int)(end - GetTickCount()) <= 0) return TRUE;
        MsgWaitForMultipleObjects(0, NULL, FALSE, 2, QS_ALLINPUT);
    }
}

static ID3D11DeviceContext *g_ctx;
static ID3D11Texture2D *g_big_a, *g_big_b;
static int g_gpu, g_cpums;

static void frame_work(void)
{
    LARGE_INTEGER f, a, b;
    int k;
    if (g_cpums) {
        QueryPerformanceFrequency(&f);
        QueryPerformanceCounter(&a);
        do { QueryPerformanceCounter(&b); } while ((b.QuadPart - a.QuadPart) * 1000 < (long long)g_cpums * f.QuadPart);
    }
    for (k = 0; k < g_gpu; k++)
        ID3D11DeviceContext_CopyResource(g_ctx, (ID3D11Resource *)((k & 1) ? g_big_a : g_big_b), (ID3D11Resource *)((k & 1) ? g_big_b : g_big_a));
}

static void put(const char *s)
{
    DWORD n;
    WriteFile(logfile, s, (DWORD)lstrlenA(s), &n, NULL);
    FlushFileBuffers(logfile);
}

static void putf(const char *tag, unsigned a, unsigned b, unsigned c)
{
    char buf[96];
    wsprintfA(buf, "%s %u %u %u\n", tag, a, b, c);
    put(buf);
}

void WINAPI WinMainCRTStartup(void)
{
    WCHAR *cmd = GetCommandLineW(), path[512];
    int bursts = 200, effect = 0, stress = 0;
    int gpu = 0, cpums = 0;
    int size, resize, minimize;
    HWND top, child;
    WNDCLASSW wc;
    DXGI_SWAP_CHAIN_DESC sd;
    IDXGISwapChain *sc = NULL;
    ID3D11Device *dev = NULL;
    ID3D11DeviceContext *ctx = NULL;
    ID3D11Texture2D *bb = NULL;
    ID3D11RenderTargetView *rtv = NULL;
    HRESULT hr;
    int b, prev = 0;
    argument(&cmd, path, 512); /* executable */
    argument(&cmd, path, 512); /* logfile, including quoted paths */
    bursts = number(&cmd, 200);
    effect = number(&cmd, 0);
    stress = number(&cmd, 0);
    gpu = number(&cmd, 0);
    cpums = number(&cmd, 0);
    size = number(&cmd, 580);
    resize = number(&cmd, 0);
    minimize = number(&cmd, 0);
    if (size < 320 || size > 580 || bursts < 1 || bursts > 10000 || effect > 1) ExitProcess(8);

    logfile = CreateFileW(path, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_ALWAYS, 0, NULL);
    if (logfile == INVALID_HANDLE_VALUE) ExitProcess(2);

    memset(&wc, 0, sizeof(wc));
    wc.lpfnWndProc = wndproc;
    wc.hInstance = GetModuleHandleW(NULL);
    wc.lpszClassName = L"SnapTop";
    RegisterClassW(&wc);
    wc.lpszClassName = L"SnapChild";
    RegisterClassW(&wc);

    top = CreateWindowExW(WS_EX_NOACTIVATE, L"SnapTop", L"SnapTest", WS_OVERLAPPEDWINDOW | WS_VISIBLE,
                          200, 150, 640, 700, NULL, NULL, wc.hInstance, NULL);
    child = CreateWindowExW(0, L"SnapChild", L"", WS_CHILD | WS_VISIBLE, 20, 20, size, size, top, NULL, wc.hInstance, NULL);
    ShowWindow(top, SW_SHOWNOACTIVATE);
    pump(500);

    memset(&sd, 0, sizeof(sd));
    sd.BufferDesc.Width = size;
    sd.BufferDesc.Height = size;
    sd.BufferDesc.Format = DXGI_FORMAT_B8G8R8A8_UNORM;
    sd.SampleDesc.Count = 1;
    sd.BufferUsage = DXGI_USAGE_RENDER_TARGET_OUTPUT;
    sd.BufferCount = effect ? 3 : 1;
    sd.OutputWindow = child;
    sd.Windowed = TRUE;
    sd.SwapEffect = effect ? DXGI_SWAP_EFFECT_FLIP_DISCARD : DXGI_SWAP_EFFECT_DISCARD;
    hr = D3D11CreateDeviceAndSwapChain(NULL, D3D_DRIVER_TYPE_HARDWARE, NULL, 0, NULL, 0, D3D11_SDK_VERSION,
                                       &sd, &sc, &dev, NULL, &ctx);
    if (FAILED(hr)) { putf("ERR", (unsigned)hr, 0, 0); ExitProcess(3); }
    hr = IDXGISwapChain_GetBuffer(sc, 0, &IID_ID3D11Texture2D, (void **)&bb);
    if (FAILED(hr)) { putf("ERR", (unsigned)hr, 1, 0); ExitProcess(4); }
    hr = ID3D11Device_CreateRenderTargetView(dev, (ID3D11Resource *)bb, NULL, &rtv);
    if (FAILED(hr)) { putf("ERR", (unsigned)hr, 2, 0); ExitProcess(5); }
    ID3D11DeviceContext_OMSetRenderTargets(ctx, 1, &rtv, NULL);
    g_ctx = ctx; g_gpu = gpu; g_cpums = cpums;
    if (gpu) {
        D3D11_TEXTURE2D_DESC td;
        memset(&td, 0, sizeof(td));
        td.Width = 8192; td.Height = 8192; td.MipLevels = 1; td.ArraySize = 1;
        td.Format = DXGI_FORMAT_B8G8R8A8_UNORM; td.SampleDesc.Count = 1;
        td.Usage = D3D11_USAGE_DEFAULT; td.BindFlags = D3D11_BIND_SHADER_RESOURCE;
        hr = ID3D11Device_CreateTexture2D(dev, &td, NULL, &g_big_a);
        if (FAILED(hr)) { putf("ERR", (unsigned)hr, 3, 0); ExitProcess(6); }
        hr = ID3D11Device_CreateTexture2D(dev, &td, NULL, &g_big_b);
        if (FAILED(hr)) { putf("ERR", (unsigned)hr, 4, 0); ExitProcess(7); }
    }

    putf("READY", (unsigned)(UINT_PTR)top, (unsigned)(UINT_PTR)child, effect);
    pump(1500);

    for (b = 0; b < bursts; b++) {
        int n = 1 + rnd() % 4, k, idx = prev;
        if (resize && b && !(b % 4)) {
            size = size == 580 ? 384 : 580;
            ID3D11DeviceContext_OMSetRenderTargets(ctx, 0, NULL, NULL);
            ID3D11RenderTargetView_Release(rtv);
            ID3D11Texture2D_Release(bb);
            SetWindowPos(child, NULL, 0, 0, size, size, SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE);
            hr = IDXGISwapChain_ResizeBuffers(sc, 0, size, size, DXGI_FORMAT_UNKNOWN, 0);
            if (FAILED(hr)) { putf("ERR", (unsigned)hr, 5, 0); ExitProcess(9); }
            hr = IDXGISwapChain_GetBuffer(sc, 0, &IID_ID3D11Texture2D, (void **)&bb);
            if (FAILED(hr)) ExitProcess(10);
            hr = ID3D11Device_CreateRenderTargetView(dev, (ID3D11Resource *)bb, NULL, &rtv);
            if (FAILED(hr)) ExitProcess(11);
            ID3D11DeviceContext_OMSetRenderTargets(ctx, 1, &rtv, NULL);
            putf("RESIZE", b, size, size);
            pump(30);
        }
        if (minimize && b && !(b % 10)) {
            ShowWindow(top, SW_MINIMIZE);
            pump(50);
            ShowWindow(top, SW_SHOWNOACTIVATE);
            pump(100);
        }
        for (k = 0; k < n; k++) {
            idx = (prev + 1 + rnd() % 7) % 8;
            prev = idx;
            frame_work();
            ID3D11DeviceContext_ClearRenderTargetView(ctx, rtv, palette[idx]);
            IDXGISwapChain_Present(sc, 0, 0);
            putf("P", (unsigned)b, (unsigned)k, (unsigned)idx);
            if (k + 1 < n && !pump(6 + rnd() % 10)) goto done;
        }
        putf("F", (unsigned)b, (unsigned)idx, (unsigned)GetTickCount());
        if (!pump(300 + rnd() % 150)) break;
    }
done:
    if (stress) {
        LARGE_INTEGER f, t0, t1;
        QueryPerformanceFrequency(&f);
        QueryPerformanceCounter(&t0);
        for (b = 0; b < stress; b++) {
            frame_work();
            ID3D11DeviceContext_ClearRenderTargetView(ctx, rtv, palette[b & 7]);
            IDXGISwapChain_Present(sc, 0, 0);
        }
        QueryPerformanceCounter(&t1);
        putf("STRESS", (unsigned)stress, (unsigned)((t1.QuadPart - t0.QuadPart) * 1000000 / f.QuadPart / stress), 0);
    }
    /* Exercise native surface detachment/destruction before process teardown;
     * otherwise ExitProcess hides lifetime bugs by leaking the COM objects. */
    ID3D11DeviceContext_ClearState(ctx);
    ID3D11DeviceContext_Flush(ctx);
    ID3D11RenderTargetView_Release(rtv);
    ID3D11Texture2D_Release(bb);
    if (g_big_a) ID3D11Texture2D_Release(g_big_a);
    if (g_big_b) ID3D11Texture2D_Release(g_big_b);
    IDXGISwapChain_Release(sc);
    ID3D11DeviceContext_Release(ctx);
    ID3D11Device_Release(dev);
    DestroyWindow(child);
    DestroyWindow(top);
    pump(100);
    put("DONE\n");
    ExitProcess(0);
}
