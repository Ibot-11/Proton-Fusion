/* SPDX-License-Identifier: MIT */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>

static LRESULT CALLBACK proc(HWND w,UINT m,WPARAM p,LPARAM l) { return DefWindowProcW(w,m,p,l); }

void WINAPI WinMainCRTStartup(void)
{
    WNDCLASSW wc={0};
    HWND owner, panel, bar, hud, other;
    UINT dpi;
    DWORD end;
    MSG message;
    SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
    wc.lpfnWndProc=proc;
    wc.hInstance=GetModuleHandleW(NULL);
    wc.lpszClassName=L"FusionPanelProbeOwner";
    RegisterClassW(&wc);
    owner=CreateWindowW(wc.lpszClassName,L"FusionPanelProbe-Owner",WS_OVERLAPPEDWINDOW,100,100,1200,900,NULL,NULL,wc.hInstance,NULL);
    ShowWindow(owner,SW_SHOWNOACTIVATE);
    dpi=GetDpiForWindow(owner);
    if (!dpi) dpi=96;
    SetWindowPos(owner,NULL,0,0,MulDiv(1200,dpi,96),MulDiv(900,dpi,96),SWP_NOMOVE|SWP_NOZORDER|SWP_NOACTIVATE);
    wc.lpszClassName=L"Qt683QWindowToolSaveBits";
    RegisterClassW(&wc);
    panel=CreateWindowExW(WS_EX_TOOLWINDOW,wc.lpszClassName,L"FusionPanelProbe-Panel",WS_POPUP,120,150,MulDiv(250,dpi,96),MulDiv(600,dpi,96),owner,NULL,wc.hInstance,NULL);
    SetWindowPos(panel,NULL,0,0,0,0,SWP_NOMOVE|SWP_NOSIZE|SWP_NOZORDER|SWP_NOACTIVATE|SWP_SHOWWINDOW);
    bar=CreateWindowExW(WS_EX_TOOLWINDOW,wc.lpszClassName,L"FusionPanelProbe-Bar",WS_POPUP,120,800,MulDiv(250,dpi,96),MulDiv(25,dpi,96),owner,NULL,wc.hInstance,NULL);
    hud=CreateWindowExW(WS_EX_TOOLWINDOW,wc.lpszClassName,L"FusionPanelProbe-HUD",WS_POPUP,600,300,MulDiv(150,dpi,96),MulDiv(45,dpi,96),owner,NULL,wc.hInstance,NULL);
    wc.lpszClassName=L"FusionPanelProbeUnrelated";
    RegisterClassW(&wc);
    other=CreateWindowExW(WS_EX_TOOLWINDOW,wc.lpszClassName,L"FusionPanelProbe-Other",WS_POPUP,900,150,MulDiv(250,dpi,96),MulDiv(600,dpi,96),owner,NULL,wc.hInstance,NULL);
    SetWindowPos(bar,NULL,0,0,0,0,SWP_NOMOVE|SWP_NOSIZE|SWP_NOZORDER|SWP_NOACTIVATE|SWP_SHOWWINDOW);
    SetWindowPos(hud,NULL,0,0,0,0,SWP_NOMOVE|SWP_NOSIZE|SWP_NOZORDER|SWP_NOACTIVATE|SWP_SHOWWINDOW);
    SetWindowPos(other,NULL,0,0,0,0,SWP_NOMOVE|SWP_NOSIZE|SWP_NOZORDER|SWP_NOACTIVATE|SWP_SHOWWINDOW);
    if ((GetWindowLongPtrW(panel,GWL_EXSTYLE)|GetWindowLongPtrW(bar,GWL_EXSTYLE)) & WS_EX_APPWINDOW) ExitProcess(20);
    end=GetTickCount()+3000;
    while ((int)(end-GetTickCount())>0) {
        while (PeekMessageW(&message,NULL,0,0,PM_REMOVE)) { TranslateMessage(&message); DispatchMessageW(&message); }
        MsgWaitForMultipleObjects(0,NULL,FALSE,5,QS_ALLINPUT);
    }
    ExitProcess(0);
}
