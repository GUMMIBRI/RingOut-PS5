// SPDX-License-Identifier: GPL-2.0-or-later
#include "moderngekko/runtime.hpp"
#include <cstdint>

int main()
{
  moderngekko::ModuleSource source;
  std::uint32_t dynamic_groups = 6;
  if (source.GuestGateGroups(&dynamic_groups) != 0) return 1;
  source.kind = moderngekko::ModuleSource::Kind::AttachedDescriptor;
  if (source.GuestGateGroups(&dynamic_groups) != 0) return 2;
  source.attached_gate_groups = 2;
  if (source.GuestGateGroups(&dynamic_groups) != 0) return 3;
  volatile std::uint32_t armed = 0, bypass = 0;
  source.attached_gate_armed = &armed;
  if (source.GuestGateGroups(&dynamic_groups) != 0) return 3;
  source.attached_gate_bypass = &bypass;
  if (source.GuestGateGroups(&dynamic_groups) != 2) return 3;
  source.attached_gate_groups = 6;
  if (source.GuestGateGroups(nullptr) != 6) return 4;
  source.kind = moderngekko::ModuleSource::Kind::DynamicPath;
  if (source.GuestGateGroups(nullptr) != 0) return 5;
  if (source.GuestGateGroups(&dynamic_groups) != 6) return 6;
  return 0;
}
