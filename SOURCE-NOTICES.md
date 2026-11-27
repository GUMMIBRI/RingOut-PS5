# RingOut 1.0 Beta source and license notices

The PS5 runtime uses GPL-3.0-or-later. RingOut, ModernGekko and Dolphin retain their upstream notices. The PS5 application PRX loader is from [PS5 Native App Boilerplate at e879c08](https://github.com/mpereiraesaa/ps5-native-app-boilerplate/tree/e879c08a408ac17186b4736d86f67bcc1aa9dab8). It is distributed under GPL-3.0-or-later.

The [matching RingOut PS5 source and build recipe](https://github.com/GUMMIBRI/RingOut-PS5/tree/release/ringout-1.0b-source) identify runtime source aa64df6d1d9457e643e8704e9be7bc2055a133c1, the baseline checkout and the exact PS5 changes. The separately generated app companion comes from [PSXS5 at 5c17ea3](https://github.com/SynoPiia/PSXS5/tree/5c17ea31aec5791c12451e915386fa98d670adb4). The supplied PS5 build uses [the public PS5 SDK v0.45](https://github.com/ps5-payload-dev/sdk/tree/v0.45) and the platform libraries from [PS5_PayloadSDK at b83202b](https://github.com/mihawk-99/PS5_PayloadSDK/tree/b83202be73e930050e00de0f1b4d9ec46c0391bf).

The Vulkan backend uses [PS5_Mesa at 7b59ef2](https://github.com/mihawk-99/PS5_Mesa/tree/7b59ef27c1b09b9671bc4153c41940c3155c3af2) and its [PS5_Vulkan build recipe at fde9e37](https://github.com/mihawk-99/PS5_Vulkan/tree/fde9e3798c2ec1d8fccc90d5067cd6060490607f). SDL3 uses the Zlib license, with the altered PS5 SDL3 source identified alongside the RingOut release source. Vendored libraries in the pinned RingOut baseline carry their own licenses and notices.

The provided GameCube DSP ROM and coefficient files are Dolphin's free replacement v0.4. Their source lives in Dolphin's docs/DSP/free_dsp_rom. The GameCube font replacements are derived from Droid Sans under Apache-2.0. Their notice is beside the font files in sys/GC.

The optional Windows setup archive includes DolRecomp under GPL-3.0-or-later and its matching source, the native converter from the pinned PS5 Native App Boilerplate release under GPL-3.0-or-later, and [zlib 1.3.2](https://zlib.net/fossils/zlib-1.3.2.tar.gz) under the zlib license. Setup creates the private game files and compiled game module from the player's discs.
