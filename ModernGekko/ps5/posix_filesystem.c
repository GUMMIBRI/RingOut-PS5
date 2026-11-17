/* SPDX-License-Identifier: GPL-3.0-or-later
 * PS5 native process/filesystem fallbacks. Unsupported operations fail explicitly.
 * pathconf delegates to the kernel's descriptor variant; opening the path may
 * require read permission, so this is narrower than POSIX pathconf semantics. */
#include <errno.h>
#include <fcntl.h>
#include <sys/types.h>
#include <unistd.h>

extern long _fpathconf(int, int);
extern int _fcntl(int, int, ...);

/* Native titles have no terminal. This follows PSXS5's console_curl.c and
 * PS5_PayloadSDK's libc/isatty.c: the WebKit POSIX export can be a null import
 * in a native title. This is a platform stand-in, not a descriptor validator. */
int ps5_isatty(int descriptor)
{
    (void)descriptor;
    errno = ENOTTY;
    return 0;
}

int ps5_dup(int fd)
{
    return _fcntl(fd, F_DUPFD, 0);
}

long ps5_pathconf(const char *path, int name)
{
    if (!path) { errno = EFAULT; return -1; }
    int fd = open(path, O_RDONLY | O_NONBLOCK);
    if (fd < 0) return -1;
    long result = _fpathconf(fd, name);
    int saved_errno = errno;
    (void)close(fd);
    errno = saved_errno;
    return result;
}

pid_t ps5_fork(void) { errno = ENOSYS; return (pid_t)-1; }
int ps5_link(const char *oldpath, const char *newpath)
{ (void)oldpath; (void)newpath; errno = ENOSYS; return -1; }
int ps5_symlink(const char *target, const char *linkpath)
{ (void)target; (void)linkpath; errno = ENOSYS; return -1; }
ssize_t ps5_readlink(const char *path, char *buf, size_t size)
{ (void)path; (void)buf; (void)size; errno = ENOSYS; return -1; }
