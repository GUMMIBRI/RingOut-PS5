/*
 * SDL PS5 static RADV Vulkan hooks.
 * Altered CPE version, 2026-10-30, based on griches/PS5_DevilutionX
 * ps5/sdl/SDL_ps5video.c at 4dc807484de4bd1c1020da3d7d67a886c9dd6c3a.
 * SPDX-License-Identifier: Zlib
 * See upstream/PS5_Dusklight-72d6885cc8b4ff4c5f6be23682ab11578ec926c4/licenses/Zlib.txt.
 */
#include "SDL_internal.h"
#if defined(SDL_VIDEO_DRIVER_PS5) && defined(SDL_VIDEO_VULKAN)
#include "video/SDL_sysvideo.h"
#include "video/SDL_vulkan_internal.h"

extern PFN_vkVoidFunction vk_icdGetInstanceProcAddr(VkInstance instance, const char *name);

static bool PS5_Vulkan_LoadLibrary(SDL_VideoDevice *device, const char *path)
{
    /* A title has no payload-injected dlopen/dlsym callbacks. The ICD is
     * linked whole and its entry point is resolved by the static linker. */
    if (path && *path && SDL_strcmp(path, "radv") != 0)
        return SDL_SetError("PS5 Vulkan accepts only the statically linked RADV driver");
    PFN_vkEnumerateInstanceExtensionProperties enumerate =
        (PFN_vkEnumerateInstanceExtensionProperties)vk_icdGetInstanceProcAddr(
            VK_NULL_HANDLE, "vkEnumerateInstanceExtensionProperties");
    if (!enumerate || !vk_icdGetInstanceProcAddr(VK_NULL_HANDLE, "vkCreateInstance"))
        return SDL_SetError("Static PS5 RADV entry points unavailable");
    Uint32 count = 0;
    VkExtensionProperties *extensions = SDL_Vulkan_CreateInstanceExtensionsList(enumerate, &count);
    if (!extensions) return false;
    bool surface = false, display = false;
    for (Uint32 i = 0; i < count; ++i) {
        surface |= SDL_strcmp(extensions[i].extensionName, VK_KHR_SURFACE_EXTENSION_NAME) == 0;
        display |= SDL_strcmp(extensions[i].extensionName, VK_KHR_DISPLAY_EXTENSION_NAME) == 0;
    }
    SDL_free(extensions);
    if (!surface || !display)
        return SDL_SetError("Static PS5 RADV requires VK_KHR_surface and VK_KHR_display");
    device->vulkan_config.vkGetInstanceProcAddr = (void *)vk_icdGetInstanceProcAddr;
    device->vulkan_config.vkEnumerateInstanceExtensionProperties = (void *)enumerate;
    SDL_strlcpy(device->vulkan_config.loader_path, "radv", sizeof(device->vulkan_config.loader_path));
    return true;
}
static void PS5_Vulkan_UnloadLibrary(SDL_VideoDevice *device)
{
    device->vulkan_config.vkGetInstanceProcAddr = NULL;
    device->vulkan_config.vkEnumerateInstanceExtensionProperties = NULL;
    device->vulkan_config.loader_path[0] = '\0';
}
static const char *const *PS5_Vulkan_GetInstanceExtensions(SDL_VideoDevice *device, Uint32 *count)
{
    (void)device;
    static const char *const names[] = {VK_KHR_SURFACE_EXTENSION_NAME, VK_KHR_DISPLAY_EXTENSION_NAME};
    if (count) *count = SDL_arraysize(names);
    return names;
}
static bool PS5_Vulkan_CreateSurface(SDL_VideoDevice *device, SDL_Window *window,
    VkInstance instance, const struct VkAllocationCallbacks *allocator, VkSurfaceKHR *surface)
{
    (void)window;
    if (!device->vulkan_config.vkGetInstanceProcAddr || !surface)
        return SDL_SetError("PS5 Vulkan surface requested without a loaded static driver");
    return SDL_Vulkan_Display_CreateSurface(device->vulkan_config.vkGetInstanceProcAddr,
        instance, allocator, surface);
}
static void PS5_Vulkan_DestroySurface(SDL_VideoDevice *device, VkInstance instance,
    VkSurfaceKHR surface, const struct VkAllocationCallbacks *allocator)
{
    if (device->vulkan_config.vkGetInstanceProcAddr && surface)
        SDL_Vulkan_DestroySurface_Internal(device->vulkan_config.vkGetInstanceProcAddr,
            instance, surface, allocator);
}
void CPE_PS5_InstallVulkanHooks(SDL_VideoDevice *device)
{
    device->Vulkan_LoadLibrary = PS5_Vulkan_LoadLibrary;
    device->Vulkan_UnloadLibrary = PS5_Vulkan_UnloadLibrary;
    device->Vulkan_GetInstanceExtensions = PS5_Vulkan_GetInstanceExtensions;
    device->Vulkan_CreateSurface = PS5_Vulkan_CreateSurface;
    device->Vulkan_DestroySurface = PS5_Vulkan_DestroySurface;
}
#endif
