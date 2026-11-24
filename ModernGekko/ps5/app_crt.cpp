/*
 * ps5-native-app-boilerplate - Native application startup.
 * Copyright (C) 2026 BlackBearReloaded
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * Initializes the platform runtime, runs static constructors and main, and
 * requests native title termination through the system service.
 */

#include <cstddef>
#include <cstdint>
#include "native_startup.h"

using Destructor = void (*)();
using Initializer = void (*)();

extern "C"
{
    void _init_env(void *process_parameters);
    int atexit(Destructor callback);
    int sceSystemServiceLoadExec(const char *path, const char **arguments);
    int sceKernelUsleep(std::uint32_t microseconds);
    int sceKernelSendNotificationRequest(std::uint32_t device, void *request,
                                         std::size_t size, int blocking);
    int application_main(int argc, char **argv, char **envp) __asm__("main");

    extern Initializer __preinit_array_start[] __attribute__((weak));
    extern Initializer __preinit_array_end[] __attribute__((weak));
    extern Initializer __init_array_start[] __attribute__((weak));
    extern Initializer __init_array_end[] __attribute__((weak));
    extern Initializer __fini_array_start[] __attribute__((weak));
    extern Initializer __fini_array_end[] __attribute__((weak));
}

namespace
{
void run_forward(Initializer *first, Initializer *last) noexcept
{
    if (first == nullptr || last == nullptr)
        return;
    while (first != last)
        (*first++)();
}

void run_reverse(Initializer *first, Initializer *last) noexcept
{
    if (first == nullptr || last == nullptr)
        return;
    while (last != first)
        (*--last)();
}
} // namespace

extern "C" __attribute__((weak)) void catchReturnFromMain(int status)
{
    (void)status;
}

extern "C" void _init()
{
    ringout_native_stage("before preinit array\n");
    run_forward(__preinit_array_start, __preinit_array_end);
    ringout_native_stage("before init array\n");
    run_forward(__init_array_start, __init_array_end);
    ringout_native_stage("after init array\n");
}

extern "C" void _fini()
{
    ringout_native_stage("before fini array\n");
    run_reverse(__fini_array_start, __fini_array_end);
    ringout_native_stage("after fini array\n");
    ringout_native_close();
}

extern "C" void ps5_fp_ieee(void);
extern "C" [[noreturn]] __attribute__((visibility("default"))) void
_start(void *process_parameters, Destructor loader_teardown)
{
    ps5_fp_ieee();
    ringout_native_stage("native entry before init_env\n");
    // Paired with this build's ELF entry value, this records the actual load
    // bias for future crash analysis instead of assuming a launcher address.
    ringout_native_value("native entry address ",
                         reinterpret_cast<std::uintptr_t>(&_start));
    const int argc = *static_cast<const int *>(process_parameters);
    auto *parameters = static_cast<std::uint8_t *>(process_parameters);
    auto **argv = reinterpret_cast<char **>(parameters + sizeof(std::uint64_t));

    _init_env(process_parameters);
    ringout_native_stage("after init_env\n");
    if (loader_teardown != nullptr)
        (void)atexit(loader_teardown);
    (void)atexit(_fini);
    _init();
    ringout_native_stage("before main\n");
    const int status = application_main(argc, argv, nullptr);
    ringout_native_value("main returned ", static_cast<unsigned>(status));
    if (status != 0)
    {
        // Notification request layout follows PSXS5's plat_notify implementation.
        static struct
        {
            std::uint8_t reserved[45];
            char message[3075];
        } notification = {{}, "RingOut could not start. Check the startup log."};
        const int notify_result = sceKernelSendNotificationRequest(0, &notification,
                                                                   sizeof(notification), 0);
        ringout_native_value("failure notification rc_u32 ",
                             static_cast<std::uint32_t>(notify_result));
    }
    catchReturnFromMain(status);
    // main has unwound its application-owned objects. Keep the registered
    // finalizers and loader_teardown under runtime ownership: invoking them
    // here would risk duplicate destruction or unloading code before LoadExec.
    // Native titles terminate through the system, not libc exit(). The shell
    // may terminate the process without running application atexit handlers.
    ringout_native_stage("requesting system exit\n");
    const int exit_result = sceSystemServiceLoadExec("exit", nullptr);
    ringout_native_value("system exit returned rc_u32 ",
                         static_cast<std::uint32_t>(exit_result));
    ringout_native_stage("waiting for shell termination\n");
    ringout_native_close();
    // The request can return before termination or fail. Preserve the log and
    // remain available for shell-mediated closure; never retry or call exit.
    for (;;)
        (void)sceKernelUsleep(1000000);
}

