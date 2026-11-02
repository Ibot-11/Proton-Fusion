/* SPDX-License-Identifier: MIT
 * Test-only X server fault injection. This library is never packaged in Proton.
 * Build as libXdamage.so.1 or libXrandr.so.2 with a renamed real dependency.
 */
#define _GNU_SOURCE
#include <X11/Xlib.h>
#include <X11/extensions/Xdamage.h>
#include <X11/extensions/Xrandr.h>
#include <dlfcn.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>

static atomic_int injected;
static int once(const char *name)
{
    return getenv(name) && !atomic_exchange(&injected, 1);
}

#ifdef FUSION_TEST_DAMAGE
Damage XDamageCreate(Display *display, Drawable drawable, int level)
{
    static Damage (*real)(Display *, Drawable, int);
    if (!real) real = dlsym(RTLD_NEXT, "XDamageCreate");
    if (once("FUSION_TEST_BAD_DRAWABLE")) {
        fprintf(stderr, "FUSION_FAULT: XDamageCreate BadDrawable\n");
        drawable = 0xdeadbeef;
    } else if (once("FUSION_TEST_UNEXPECTED_XERROR")) {
        fprintf(stderr, "FUSION_FAULT: unexpected BadAtom\n");
        XDeleteProperty(display, drawable, 0xdeadbeef);
    }
    return real(display, drawable, level);
}

void XDamageDestroy(Display *display, Damage damage)
{
    static void (*real)(Display *, Damage);
    if (!real) real = dlsym(RTLD_NEXT, "XDamageDestroy");
    if (once("FUSION_TEST_BAD_DAMAGE_DESTROY")) {
        fprintf(stderr, "FUSION_FAULT: XDamageDestroy BadDamage\n");
        real(display, damage);
    }
    real(display, damage);
}

void XDamageSubtract(Display *display, Damage damage, XserverRegion repair, XserverRegion parts)
{
    static void (*real)(Display *, Damage, XserverRegion, XserverRegion);
    static void (*destroy)(Display *, Damage);
    if (!real) real = dlsym(RTLD_NEXT, "XDamageSubtract");
    if (!destroy) destroy = dlsym(RTLD_NEXT, "XDamageDestroy");
    if (once("FUSION_TEST_BAD_DAMAGE_SUBTRACT")) {
        fprintf(stderr, "FUSION_FAULT: XDamageSubtract BadDamage\n");
        destroy(display, damage);
    }
    real(display, damage, repair, parts);
}
#else
XRRCrtcInfo *XRRGetCrtcInfo(Display *display, XRRScreenResources *resources, RRCrtc crtc)
{
    static XRRCrtcInfo *(*real)(Display *, XRRScreenResources *, RRCrtc);
    if (!real) real = dlsym(RTLD_NEXT, "XRRGetCrtcInfo");
    if (once("FUSION_TEST_BAD_CRTC")) {
        fprintf(stderr, "FUSION_FAULT: RRGetCrtcInfo BadRRCrtc\n");
        crtc = 0xdeadbeef;
    }
    return real(display, resources, crtc);
}
#endif
