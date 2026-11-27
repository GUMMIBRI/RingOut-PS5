# Platform build inputs

Use the pinned SDK, RADV, and platform libraries in [SOURCE-NOTICES.md](../SOURCE-NOTICES.md). Restore the SDL baseline `fa2c02bb6e21974a89ea9824bc53c9932abe5f9c`, then apply the files in `sdl3-overlay/` and build SDL as a static library with the flags in `build-sdl.ps1`. The overlay already contains the generated PS5 Vulkan changes, so skip the `prepare-sdl.cjs` step when using it.

Keep external module loading enabled in the ModernGekko configuration. See `configure-host.json` for the CMake arguments; replace the path variables with your checkout and tool locations. Build and attest the host first. Use the same path layout in the current Windows-native link recipe or adapt its workspace and platform paths together.

```powershell
python ModernGekko/ps5/attest-host-build.py --host-build PATH_TO_HOST_BUILD --jobs 4
python ModernGekko/ps5/build-native.py --stage NEW_STAGE --build-id external-prx-20261127-r4 --host-build PATH_TO_HOST_BUILD --include-ps5-menu --trace-boot --trace-vulkan --managed-worker-stack --use-title-heap
```

Source for the PS5 app converter and loader companion is in the pinned PSXS5 checkout. The linked SDK libc archive is the SDK's `libc.a` with `dlfcn.o` removed. The player-prepared PRX is built separately with the pinned Native App Boilerplate converter. The PS5 EBOOT link uses the external module path and has no player game archive input.
