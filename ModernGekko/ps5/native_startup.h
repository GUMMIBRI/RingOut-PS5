// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

// Current private USB0 app contract. An absolute argv[0] still selects game/user roots.
#ifndef RINGOUT_APP_ROOT
#define RINGOUT_APP_ROOT "/mnt/usb0/homebrew/PPSA99875"
#endif
#ifndef RINGOUT_BUILD_ID
#define RINGOUT_BUILD_ID "unversioned-local"
#endif

#ifdef __cplusplus
extern "C" {
#endif
void ringout_native_stage(const char* message);
void ringout_native_value(const char* label, unsigned long long value);
void ringout_native_close(void);
#ifdef __cplusplus
}
#endif
