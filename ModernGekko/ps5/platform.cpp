// SPDX-License-Identifier: GPL-2.0-or-later
#include <chrono>
#include <atomic>
#include <memory>
#include <thread>

#include "Core/Core.h"
#include "Core/System.h"
#include "DolphinNoGUI/Platform.h"
#include "VideoCommon/RecompMenu.h"

namespace
{
class PlatformPS5 final : public Platform
{
public:
  PlatformPS5() { m_window_fullscreen = true; }

  void MainLoop() override
  {
    auto& system = Core::System::GetInstance();
    // QuitOnceResumed may invoke a copied callback on a detached worker after
    // this loop exits. Keep its signal alive independently of the platform.
    const auto menu_quit = std::make_shared<std::atomic<bool>>(false);
    RecompMenu::SetQuitCallback([menu_quit] { menu_quit->store(true); });
    while (IsRunning())
    {
      if (menu_quit->exchange(false))
        RequestShutdown();
      UpdateRunningFlag();
      if (!IsRunning())
        break;
      Core::HostDispatchJobs(system);
      RecompMenu::HostTick();
      if (RecompMenu::IsOpen())
        RecompMenu::PumpFrame();
      std::this_thread::sleep_for(std::chrono::milliseconds(8));
    }
    RecompMenu::SetQuitCallback({});
  }

  WindowSystemInfo GetWindowSystemInfo() const override
  {
    return {WindowSystemType::Display, nullptr, nullptr, nullptr};
  }
};
}  // namespace

std::unique_ptr<Platform> Platform::CreatePS5Platform()
{
  return std::make_unique<PlatformPS5>();
}
