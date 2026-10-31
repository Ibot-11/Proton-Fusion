/* SPDX-License-Identifier: MIT */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winstring.h>

void WINAPI WinMainCRTStartup(void)
{
    typedef HRESULT (WINAPI *get_languages)(WCHAR,HSTRING *);
    HMODULE dll = LoadLibraryW(L"bcp47langs.dll");
    get_languages get = dll ? (get_languages)GetProcAddress(dll,"GetUserLanguages") : NULL;
    WCHAR expected[1024], *src;
    const WCHAR *actual;
    ULONG count, size;
    UINT32 length;
    HSTRING value;
    WCHAR delimiters[] = {';', '|'};
    int i, offset;
    DWORD written;
    if (!get) ExitProcess(10);
    for (i=0;i<2;i++) {
        size=1024;
        if (!GetUserPreferredUILanguages(MUI_LANGUAGE_NAME,&count,expected,&size)) ExitProcess(11);
        value=NULL;
        if (get(delimiters[i],&value)!=S_OK || !value) ExitProcess(12);
        actual=WindowsGetStringRawBuffer(value,&length);
        offset=0;
        for (src=expected;*src;) {
            while (*src) if (offset >= length || actual[offset++] != *src++) ExitProcess(13);
            if (*++src && (offset >= length || actual[offset++] != delimiters[i])) ExitProcess(14);
        }
        if (offset != length) ExitProcess(15);
        WindowsDeleteString(value);
    }
    WriteFile(GetStdHandle(STD_OUTPUT_HANDLE),"BCP47 preferred languages: PASS\n",31,&written,NULL);
    ExitProcess(0);
}
