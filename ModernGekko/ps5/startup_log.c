// SPDX-License-Identifier: GPL-2.0-or-later
#include "startup_log.h"

#include <inttypes.h>
#include <stdint.h>
#include <string.h>

enum { SlotCount = 6, ByteLimit = 64 * 1024 };

int ringout_log_open(RingOutStartupLog* log, const char* directory)
{
    char path[1024];
    uint64_t newest = 0;
    unsigned next = 0;
    *log = (RingOutStartupLog){0};

    for (unsigned slot = 0; slot < SlotCount; ++slot)
    {
        int length = snprintf(path, sizeof(path), "%s/startup-%u.log", directory, slot);
        if (length < 0 || (size_t)length >= sizeof(path))
            return -1;

        FILE* previous = fopen(path, "rb");
        if (previous)
        {
            uint64_t generation = 0;
            if (fscanf(previous, "run %" SCNu64, &generation) == 1 && generation > newest)
            {
                newest = generation;
                next = (slot + 1) % SlotCount;
            }
            fclose(previous);
        }
    }

    if (newest == UINT64_MAX)
        return -1;

    snprintf(path, sizeof(path), "%s/startup-%u.log", directory, next);
    log->file = fopen(path, "wb");
    if (!log->file)
        return -1;

    int length = fprintf(log->file, "run %" PRIu64 "\n", newest + 1);
    if (length < 0 || fflush(log->file) != 0)
    {
        ringout_log_close(log);
        return -1;
    }

    log->remaining = ByteLimit - (size_t)length;
    return 0;
}

int ringout_log_write(RingOutStartupLog* log, const char* message)
{
    if (!log->file)
        return -1;

    size_t length = strlen(message);
    if (length > log->remaining)
        length = log->remaining;

    size_t written = fwrite(message, 1, length, log->file);
    log->remaining -= written;
    int flush_status = fflush(log->file);
    return written == length && flush_status == 0 ? 0 : -1;
}

int ringout_log_close(RingOutStartupLog* log)
{
    int status = log->file ? fclose(log->file) : 0;
    *log = (RingOutStartupLog){0};
    return status;
}
