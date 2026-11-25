// SPDX-License-Identifier: GPL-2.0-or-later
#include "moderngekko/runtime.hpp"
#include "native_startup.h"

extern "C" {
#include "startup_log.h"
const ModernGekkoModuleDesc* staticrecomp_get_module(void);
extern const unsigned int staticrecomp_gate_groups __attribute__((weak));
extern volatile unsigned int dolrecomp_gate_armed __attribute__((weak));
extern volatile unsigned int dolrecomp_gate_bypass __attribute__((weak));
}

#include <exception>
#include <filesystem>
#include <utility>

int main(int argc, char** argv)
{
    ringout_native_stage("main entered\n");
    ringout_native_value("argc ", static_cast<unsigned>(argc));
    if ((argc != 1 && argc != 3) || !argv || !argv[0] ||
        (argc == 3 && (!argv[1] || !argv[2])))
    {
        ringout_native_stage("Invalid launch arguments\n");
        std::fputs("Usage: RingOut [<game-directory> <user-directory>]\n", stderr);
        return 2;
    }
    RingOutStartupLog log{};
    if (ringout_log_open(&log, nullptr) != 0)
        std::fputs("RingOut: could not open startup log\n", stderr);

    int status = 1;
    try
    {
        // Launchers may pass only eboot.bin. Resolving it via current_path invoked
        // libc's raw pathconf syscall before any diagnostics. Use the known app
        // contract in that case; absolute executable paths remain portable.
        const std::filesystem::path executable(argv[0]);
        const auto app_directory = executable.is_absolute() ? executable.parent_path() :
                                                              std::filesystem::path(RINGOUT_APP_ROOT);
        ringout_log_write(&log, "App directory ");
        ringout_log_write(&log, app_directory.string().c_str());
        ringout_log_write(&log, "\n");
        const std::filesystem::path game_directory = argc == 3 ? argv[1] : app_directory / "game";
        const std::filesystem::path user_directory = argc == 3 ? argv[2] : app_directory / "user";
        std::error_code error;
        std::filesystem::create_directories(user_directory, error);
        if (error)
        {
            ringout_log_write(&log, "Could not create user directory ");
            ringout_log_write(&log, error.message().c_str());
            return 2;
        }
        ringout_log_write(&log, "Creating RingOut runtime\n");
        moderngekko::RuntimeConfig config;
        config.game_root = game_directory;
        config.user_directory = user_directory;
        ringout_log_write(&log, "Attaching recompiled game module\n");
        const unsigned int gate_groups = &staticrecomp_gate_groups ? staticrecomp_gate_groups : 0u;
        config.module = moderngekko::ModuleSource::AttachedDescriptor(
            staticrecomp_get_module(), gate_groups, &dolrecomp_gate_armed, &dolrecomp_gate_bypass);
        config.graphics.backend = "Vulkan";
        // Leave the optional scale unset so Dolphin loads the saved setting;
        // its own default is 1x when the user has not chosen a scale.
        config.show_fps_in_title = false;
        ringout_log_write(&log, "Creating runtime; requested graphics backend Vulkan\n");
        auto result = moderngekko::Runtime::Create(std::move(config));
        if (result)
        {
            ringout_log_write(&log, "Starting game\n");
            const auto run = result.runtime->Run();
            if (run.error)
                ringout_log_write(&log, run.error->message.c_str());
            else if (run.reason == moderngekko::RuntimeExitReason::Stopped)
                status = 0;
        }
        else if (result.error)
        {
            ringout_log_write(&log, result.error->message.c_str());
        }
    }
    catch (const std::exception& error)
    {
        ringout_log_write(&log, error.what());
    }

    ringout_log_write(&log, status == 0 ? "\nRuntime stopped\n" : "\nRuntime failed\n");
    return ringout_log_close(&log) == 0 ? status : 1;
}
