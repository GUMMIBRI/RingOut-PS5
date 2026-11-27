// SPDX-License-Identifier: GPL-3.0-or-later
#include "moderngekko/module_abi.h"
#include "prx_loader.h"

extern const ModernGekkoModuleDesc* staticrecomp_get_module(void);
extern const uint32_t staticrecomp_gate_groups;
extern const uint32_t staticrecomp_timing_id;
extern const uint32_t staticrecomp_dyn_loop_budget;
extern volatile uint32_t dolrecomp_gate_armed;
extern volatile uint32_t dolrecomp_gate_bypass;

// These two exports are taken by address, then called by the runtime with
// their existing typed CPU-hook signatures.
extern void ppc_set_gather_pipe(uint8_t**, uint8_t* const*, void (*)(void*), void*,
                               const unsigned char*);
extern void ppc_set_mem_write_journal(void (*)(uint32_t, uint32_t, void*), void*);

PRX_DEFINE_DESCRIPTOR(ringout_prx_exports,
                      PRX_EXPORT(staticrecomp_get_module),
                      PRX_EXPORT(staticrecomp_gate_groups),
                      PRX_EXPORT(staticrecomp_timing_id),
                      PRX_EXPORT(staticrecomp_dyn_loop_budget),
                      PRX_EXPORT(dolrecomp_gate_armed),
                      PRX_EXPORT(dolrecomp_gate_bypass),
                      PRX_EXPORT(ppc_set_gather_pipe),
                      PRX_EXPORT(ppc_set_mem_write_journal));

int module_start(size_t size, const void* args)
{
  (void)size;
  (void)args;
  return 0;
}

int module_stop(size_t size, const void* args)
{
  (void)size;
  (void)args;
  return 0;
}
