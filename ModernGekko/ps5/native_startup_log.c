// SPDX-License-Identifier: GPL-2.0-or-later
// Native entry logging cannot use libc, TLS, heap, errno, or constructors.
// Six app-root slots, at most 64 KiB each, shared with the regular main logger.
#include "native_startup.h"
#include "startup_log.h"
#include <stdint.h>

extern int sceKernelOpen(const char*, int, unsigned);
extern long sceKernelRead(int, void*, size_t);
extern long sceKernelWrite(int, const void*, size_t);
extern int sceKernelClose(int);
extern int sceKernelFsync(int);

enum { SlotCount = 6, ByteLimit = 64 * 1024 };
static int descriptor = -1;
static int attempted;
static size_t remaining;

static void slot_path(char* path, unsigned slot)
{
    const char* prefix = RINGOUT_APP_ROOT "/startup-";
    while (*prefix) *path++ = *prefix++;
    *path++ = (char)('0' + slot);
    const char* suffix = ".log";
    while (*suffix) *path++ = *suffix++;
    *path = 0;
}

static int generation(int fd, uint64_t* value)
{
    char header[32];
    size_t count = 0;
    // Handle short reads. An interrupted/invalid header is never a valid generation.
    while (count < sizeof(header))
    {
        long n = sceKernelRead(fd, header + count, 1);
        if (n != 1) return 0;
        if (header[count++] == '\n') break;
    }
    if (count < 6 || header[0] != 'r' || header[1] != 'u' ||
        header[2] != 'n' || header[3] != ' ' || header[count - 1] != '\n') return 0;
    uint64_t result = 0;
    for (size_t i = 4; i + 1 < count; ++i)
    {
        if (header[i] < '0' || header[i] > '9') return 0;
        unsigned digit = (unsigned)(header[i] - '0');
        if (result > (UINT64_MAX - digit) / 10) return 0;
        result = result * 10 + digit;
    }
    *value = result;
    return 1;
}

static int write_message(const char* message)
{
    if (descriptor < 0 || !message) return -1;
    size_t length = 0;
    while (length < remaining && message[length]) ++length;
    while (length)
    {
        long n = sceKernelWrite(descriptor, message, length);
        if (n <= 0 || (size_t)n > length) return -1;
        remaining -= (size_t)n;
        length -= (size_t)n;
        message += n;
    }
    return sceKernelFsync(descriptor) < 0 ? -1 : 0;
}

static int write_value(const char* label, uint64_t value)
{
    char digits[22];
    unsigned at = sizeof(digits) - 1;
    digits[at] = 0;
    digits[--at] = '\n';
    do { digits[--at] = (char)('0' + value % 10); value /= 10; } while (value);
    if (write_message(label) < 0) return -1;
    return write_message(digits + at);
}

static int open_session(void)
{
    if (attempted) return descriptor;
    attempted = 1;
    char path[sizeof(RINGOUT_APP_ROOT) + 24];
    uint64_t newest = 0;
    uint64_t oldest = UINT64_MAX;
    int next = -1;
    int empty = -1;
    for (unsigned slot = 0; slot < SlotCount; ++slot)
    {
        slot_path(path, slot);
        int fd = sceKernelOpen(path, 0, 0); // SDK O_RDONLY
        if (fd < 0)
        {
            // Only ENOENT establishes an unused slot. Preserve unreadable evidence.
            if ((fd == -2 || (unsigned)fd == 0x80020002u) && empty < 0) empty = (int)slot;
            continue;
        }
        uint64_t value = 0;
        int valid = generation(fd, &value);
        (void)sceKernelClose(fd);
        if (!valid) continue;
        if (value > newest) newest = value;
        if (value < oldest) { oldest = value; next = (int)slot; }
    }
    if (newest == UINT64_MAX) return -1;
    if (empty >= 0) next = empty;
    if (next < 0) return -1;
    slot_path(path, (unsigned)next);
    // SDK O_WRONLY | O_CREAT | O_TRUNC. Only this project's bounded log slot is replaced.
    descriptor = sceKernelOpen(path, 0x601, 0666);
    if (descriptor >= 0)
    {
        remaining = ByteLimit;
        if (write_value("run ", newest + 1) < 0 ||
            write_message("RingOut " RINGOUT_BUILD_ID "\n") < 0)
        {
            (void)sceKernelClose(descriptor);
            descriptor = -1;
        }
    }
    return descriptor;
}

void ringout_native_stage(const char* message)
{
    if (open_session() >= 0) (void)write_message(message);
}

void ringout_native_value(const char* label, unsigned long long value)
{
    if (open_session() >= 0) (void)write_value(label, value);
}

void ringout_native_close(void)
{
    if (descriptor >= 0) (void)sceKernelClose(descriptor);
    descriptor = -1;
}

int ringout_log_open(RingOutStartupLog* log, const char* directory)
{
    // Native startup and main share one slot even before user-directory creation.
    (void)directory;
    log->file = NULL;
    int fd = open_session();
    log->remaining = remaining;
    return fd < 0 ? -1 : 0;
}

int ringout_log_write(RingOutStartupLog* log, const char* message)
{
    int result = write_message(message);
    log->remaining = remaining;
    return result;
}

int ringout_log_close(RingOutStartupLog* log)
{
    // The CRT still records main's return and destructors; it closes the descriptor.
    log->remaining = remaining;
    return descriptor < 0 ? 0 : sceKernelFsync(descriptor);
}
