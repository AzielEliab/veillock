/* Redirect open() of /dev/video* to the VeilLock device.
 *
 * This is for a process the user launched with `veillock engulf`.
 * It does not hide devices from readdir, and it does not wrap
 * PipeWire, PulseAudio, or /dev/snd.
 *
 * Build:
 *   gcc -shared -fPIC -o libveilcapture.so engulf/libveilcapture.c -ldl
 *
 * Author: Aziel Eliab.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>

static int (*real_open)(const char *, int, ...) = 0;
static int (*real_open64)(const char *, int, ...) = 0;
static int (*real_openat)(int, const char *, int, ...) = 0;
static int (*real_openat64)(int, const char *, int, ...) = 0;

static void resolve(void) {
    if (!real_open) {
        real_open = (int (*)(const char *, int, ...)) dlsym(RTLD_NEXT, "open");
    }
    if (!real_open64) {
        real_open64 = (int (*)(const char *, int, ...)) dlsym(RTLD_NEXT, "open64");
    }
    if (!real_openat) {
        real_openat = (int (*)(int, const char *, int, ...)) dlsym(RTLD_NEXT, "openat");
    }
    if (!real_openat64) {
        real_openat64 = (int (*)(int, const char *, int, ...)) dlsym(RTLD_NEXT, "openat64");
    }
}

static const char *redirect_video(const char *path) {
    const char *repl;
    if (!path) {
        return path;
    }
    repl = getenv("VEILLOCK_VIDEO");
    if (!repl || !repl[0]) {
        return path;
    }
    if (strncmp(path, "/dev/video", 10) == 0) {
        return repl;
    }
    return path;
}

static int call_open(int (*fn)(const char *, int, ...), const char *path, int flags, va_list ap) {
    mode_t mode = 0;
    if (flags & O_CREAT) {
        mode = (mode_t) va_arg(ap, int);
    }
    return fn(redirect_video(path), flags, mode);
}

int open(const char *path, int flags, ...) {
    va_list ap;
    int fd;
    resolve();
    va_start(ap, flags);
    fd = call_open(real_open, path, flags, ap);
    va_end(ap);
    return fd;
}

int open64(const char *path, int flags, ...) {
    va_list ap;
    int fd;
    resolve();
    va_start(ap, flags);
    fd = call_open(real_open64 ? real_open64 : real_open, path, flags, ap);
    va_end(ap);
    return fd;
}

static int call_openat(int (*fn)(int, const char *, int, ...), int dirfd, const char *path, int flags, va_list ap) {
    mode_t mode = 0;
    if (flags & O_CREAT) {
        mode = (mode_t) va_arg(ap, int);
    }
    return fn(dirfd, redirect_video(path), flags, mode);
}

int openat(int dirfd, const char *path, int flags, ...) {
    va_list ap;
    int fd;
    resolve();
    va_start(ap, flags);
    fd = call_openat(real_openat, dirfd, path, flags, ap);
    va_end(ap);
    return fd;
}

int openat64(int dirfd, const char *path, int flags, ...) {
    va_list ap;
    int fd;
    resolve();
    va_start(ap, flags);
    fd = call_openat(real_openat64 ? real_openat64 : real_openat, dirfd, path, flags, ap);
    va_end(ap);
    return fd;
}
