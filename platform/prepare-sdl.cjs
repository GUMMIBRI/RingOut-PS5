// CPE isolated SDL GPU preparation; no changes to the known CPU SDL install.
const fs = require('fs'), path = require('path');
const root = __dirname;
const sdl = path.join(root, 'sdl3-src');
const dusklight = path.join(root, 'upstream/PS5_Dusklight-72d6885cc8b4ff4c5f6be23682ab11578ec926c4');
let video = fs.readFileSync(path.join(dusklight, 'ps5/sdl/SDL_ps5video.c'), 'utf8');
video = video.replace(' * SPDX-License-Identifier: Zlib', ' * Altered CPE version: static RADV hooks installed; no software scanout.\n * SPDX-License-Identifier: Zlib');
video = video.replace('static SDL_VideoDevice *PS5_CreateDevice(void)',
    'extern void CPE_PS5_InstallVulkanHooks(SDL_VideoDevice *device);\n\nstatic SDL_VideoDevice *PS5_CreateDevice(void)');
video = video.replace('    device->VideoInit = PS5_VideoInit;',
    '    CPE_PS5_InstallVulkanHooks(device);\n    device->VideoInit = PS5_VideoInit;');
fs.writeFileSync(path.join(sdl, 'src/video/ps5/SDL_ps5video.c'), video);
fs.copyFileSync(path.join(root, 'sdl-port/SDL_ps5vulkan.c'), path.join(sdl, 'src/video/ps5/SDL_ps5vulkan.c'));
// Keep the public audio, joystick, time, filesystem and storage drivers as is.
let cmake = fs.readFileSync(path.join(sdl, 'pe-public-ps5.cmake'), 'utf8');
cmake = cmake.replace(/sdl_glob_sources\("\$\{SDL3_SOURCE_DIR\}\/src\/video\/ps5\/\*\.c"\s*"\$\{SDL3_SOURCE_DIR\}\/src\/video\/ps5\/\*\.h"\)/,
    'sdl_sources("${SDL3_SOURCE_DIR}/src/video/ps5/SDL_ps5video.c" "${SDL3_SOURCE_DIR}/src/video/ps5/SDL_ps5vulkan.c")');
fs.writeFileSync(path.join(sdl, 'pe-public-ps5.cmake'), cmake);
cmake = cmake.replace('set(SDL_LOADSO_DLOPEN 1)\nsdl_sources("${SDL3_SOURCE_DIR}/src/loadso/dlopen/SDL_sysloadso.c")',
    'set(SDL_LOADSO_DUMMY 1)\nsdl_sources("${SDL3_SOURCE_DIR}/src/loadso/dummy/SDL_sysloadso.c")');
fs.writeFileSync(path.join(sdl, 'pe-public-ps5.cmake'), cmake);
const mark = '# CPE_STATIC_RADV';
if (!cmake.includes(mark)) {
    cmake += `\n${mark}\nset(SDL_VIDEO_VULKAN 1)\nset(HAVE_VULKAN TRUE)\nset(SDL_GPU_VULKAN 1)\nset(SDL_GPU_ENABLED_BY_DEFAULT TRUE)\nset(HAVE_SDL_GPU TRUE)\n`;
    fs.writeFileSync(path.join(sdl, 'pe-public-ps5.cmake'), cmake);
}
// PS5 is a native CMake target, with no host window system. Permit the
// Vulkan dependency option so common SDL_GPU compilation isn't disabled.
let main = fs.readFileSync(path.join(sdl, 'CMakeLists.txt'), 'utf8');
main = main.replace('ANDROID OR APPLE OR LINUX OR FREEBSD OR OPENBSD OR WINDOWS"',
                    'ANDROID OR APPLE OR LINUX OR FREEBSD OR OPENBSD OR WINDOWS OR PS5"');
main = main.replace('set(HAVE_SDL_PROCESS TRUE)\nelseif(NOT ANDROID)',
    'set(HAVE_SDL_PROCESS TRUE)\nelseif(NOT ANDROID AND NOT PS5)');
fs.writeFileSync(path.join(sdl, 'CMakeLists.txt'), main);
console.log('Prepared static RADV SDL3 video hooks; original platform services retained.');
