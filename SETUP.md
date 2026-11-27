# Set up RingOut 1.0 Beta

RingOut is an unofficial PS5 homebrew port of the US GameCube version of Soulcalibur II. This beta requires your own US GameCube disc image (`GRSEAF`) and one Windows PC preparation step.

1. Extract the PS5 ZIP to the USB drive's `homebrew` folder. On the PS5, the executable should be at `/mnt/usb0/homebrew/PPSA99875/eboot.bin`. Keep the included `sys`, `sce_sys` and `sce_module/libc.prx` in place.
2. Extract the separate **Windows Setup Kit** on your PC. Install Python 3.11 or newer, CMake, Ninja, Windows LLVM, and the public PS5 SDK v0.45. If you want Spawn or Heihachi, install Zig as well. Either add CMake, Ninja and Zig to PATH or supply their executable paths to the setup script.
3. Put any optional Soulcalibur II Xbox ISO/XISO and US PS2 ISO beside your GameCube ISO. The setup detects one supported donor of each kind in that folder. Use `--spawn` or `--heihachi` to select a specific ISO or extracted disc folder. Use `--stock` for the GameCube roster only. Link comes with the GameCube roster.

Open PowerShell in the Windows Setup Kit and run this command with your own paths. Use a new output folder.

```powershell
py -3 setup-ringout.py "D:\Discs\Soulcalibur II USA GameCube.iso" --output "D:\RingOutData" --sdk "D:\Tools\ps5-payload-sdk" --llvm "C:\Program Files\LLVM\bin"
```

After the script prints **Ready to copy**, copy these files while RingOut is closed.

| Windows output | PS5 destination |
| --- | --- |
| `D:\RingOutData\game` | `/mnt/usb0/homebrew/PPSA99875/game/` |
| `D:\RingOutData\sce_module\gGRSEAF_recomp.prx` | `/mnt/usb0/homebrew/PPSA99875/sce_module/gGRSEAF_recomp.prx` |

Leave the existing `user/` folder in place. Your GameCube saves are under `user/GC/USA/Card A/`. After setup, the prepared game files and the player-generated PRX are all the console needs. Spawn and Heihachi are stored in `game/guests/root-guests.olk` and `game/guests/guests.json`. Keep both files together. You can remove the Xbox and PS2 ISO copies from your working folder after you verify the fighters in-game.

For optional HD textures, put each compatible pack in its own folder in `/mnt/usb0/homebrew/PPSA99875/user/Load/Mods/`. In-game, press **L3 + R3**, open **Mods**, and enable **HD texture pack** and the pack you want. Turn off **HD texture pack** to restore the original textures.

Thanks to xensavage for all of the help.
