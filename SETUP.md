# Set up RingOut on USB0

Place the RingOut app folder at `/mnt/usb0/homebrew/PPSA99875/` so `eboot.bin` sits directly inside it. If you already have RingOut installed, back up your `user` folder before updating. It contains your saves and settings.

On Windows, extract the PC data-prep kit. Install Python 3.11 or later and open PowerShell in the folder containing `prepare-ringout.py`. Use your own US GameCube disc image (`GRSEAF`) and substitute your paths in the commands below. Link is included with the GameCube roster.

```powershell
py -3 prepare-ringout.py prepare "D:\Discs\Soulcalibur II USA GameCube.iso" --output "D:\RingOutData"
```

To include Heihachi and Spawn, use the following command for the preparation step. Supply your own US PS2 disc image, extracted Xbox game folder and Zig compiler. The Xbox folder needs `root.olk` and the game executable.

```powershell
py -3 prepare-ringout.py prepare "D:\Discs\Soulcalibur II USA GameCube.iso" --output "D:\RingOutData" --heihachi "D:\Discs\Soulcalibur II USA PS2.iso" --spawn "D:\Discs\Soulcalibur II Xbox" --cc "C:\Tools\zig\zig.exe"
```

Check the prepared files before copying them.

```powershell
py -3 prepare-ringout.py check "D:\RingOutData\game"
```

With RingOut closed, copy the prepared `game` folder beside `eboot.bin`. The optional fighters use `game/guests/root-guests.olk` and `game/guests/guests.json`. Keep your original disc images on your PC. Leave your existing `user/GC/USA/Card A/` folder in place to keep your saves.

For optional HD textures, place each compatible mod in its own folder under `user/Load/Mods/`. Launch RingOut, press **L3 + R3**, open **Mods**, and use **Cross** to enable **HD texture pack** and each pack you want. Turn the master switch off to restore the original textures.

Thanks to xensavage for all of the help.
