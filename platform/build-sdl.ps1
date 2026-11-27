[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$root=$PSScriptRoot.Replace('\','/')
$sdk="$root/deps/ps5-payload-sdk"
$llvm="$root/deps/llvm/bin"
$cmake='C:/.pe/tools/cmake/cmake-4.4.4-windows-x86_64/bin/cmake.exe'
& node "$root/prepare-sdl.cjs"
if($LASTEXITCODE){throw 'SDL prepare failed'}
$priorPath=$env:PATH
try {
 $env:PATH="$llvm;$priorPath"
 & $cmake -S "$root/sdl3-src" -B "$root/build-sdl" -G Ninja '-DCMAKE_MAKE_PROGRAM=C:/.pe/tools/ninja/ninja.exe' "-DCMAKE_TOOLCHAIN_FILE=$sdk/toolchain/prospero.cmake" "-DPS5_PAYLOAD_SDK=$sdk" "-DCMAKE_AR=$llvm/llvm-ar.exe" "-DCMAKE_RANLIB=$llvm/llvm-ranlib.exe" "-DCMAKE_INSTALL_PREFIX=$root/install-sdl" '-DCMAKE_BUILD_TYPE=Release' '-DCMAKE_C_FLAGS=-std=gnu11' '-DSDL_UNIX_CONSOLE_BUILD=ON' '-DSDL_SHARED=OFF' '-DSDL_STATIC=ON' '-DSDL_TESTS=OFF' '-DSDL_TEST_LIBRARY=OFF' '-DSDL_EXAMPLES=OFF' '-DSDL_GPU=ON' '-DSDL_VULKAN=ON' '-DSDL_RENDER=ON' '-DSDL_RENDER_GPU=ON' '-DSDL_RENDER_VULKAN=OFF' '-DSDL_OPENGL=OFF' '-DSDL_OPENGLES=OFF' '-DSDL_OFFSCREEN=OFF' '-DSDL_DUMMYVIDEO=OFF' '-DSDL_DUMMYAUDIO=OFF' '-DSDL_DISKAUDIO=OFF' '-DSDL_HAPTIC=OFF' '-DSDL_SENSOR=OFF' '-DSDL_CAMERA=OFF' '-DSDL_DIALOG=OFF' '-DSDL_HIDAPI=OFF' '-DSDL_POWER=OFF' '-DSDL_PROCESS=OFF' '-DSDL_LOADSO=OFF' '-DSDL_ASSEMBLY=OFF' '-DSDL_CCACHE=OFF' *> "$root/CONFIGURE-SDL.txt"
 if($LASTEXITCODE){throw 'SDL configure failed'}
 & $cmake --build "$root/build-sdl" --parallel 4 *> "$root/BUILD-SDL.txt"
 if($LASTEXITCODE){throw 'SDL build failed'}
 & $cmake --install "$root/build-sdl" *> "$root/INSTALL-SDL.txt"
 if($LASTEXITCODE){throw 'SDL install failed'}
} finally {$env:PATH=$priorPath}
