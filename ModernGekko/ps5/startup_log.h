// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <stddef.h>
#include <stdio.h>

// One writer per app instance. The caller supplies a private, writable log directory.
typedef struct RingOutStartupLog
{
    FILE* file;
    size_t remaining;
} RingOutStartupLog;

int ringout_log_open(RingOutStartupLog* log, const char* directory);
int ringout_log_write(RingOutStartupLog* log, const char* message);
int ringout_log_close(RingOutStartupLog* log);
