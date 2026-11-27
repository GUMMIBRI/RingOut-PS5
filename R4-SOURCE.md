# RingOut PS5 1.0 Beta source

[Setup](SETUP.md) · [Beta notes](RELEASE-1.0b.md) · [Source and license notices](SOURCE-NOTICES.md)

The port source for **external-prx-20261127-r4** is the upstream [RingOut checkout at 9339899](https://github.com/jackpoison-prog/RingOut/tree/9339899231d9cf90282c7b4c17eb1cf0c3c4e14c) with `ringout-r4.patch` applied. The patch is against the original upstream checkout and replaces the earlier `tracked-changes.patch` and `weapon-master-fix.patch` for this release. Apply only `ringout-r4.patch` to that baseline.

```sh
git clone https://github.com/jackpoison-prog/RingOut.git RingOut
git -C RingOut checkout 9339899231d9cf90282c7b4c17eb1cf0c3c4e14c
git -C RingOut apply /path/to/ringout-r4.patch
```

The tested PS5 source revision was `aa64df6d1d9457e643e8704e9be7bc2055a133c1`. The patch omits Windows PGO binaries, which the PS5 host and player module builds do not consume. There are no game files or generated game modules in this source package.

The paired PS5 build used `ModernGekko/ps5/attest-host-build.py` and `ModernGekko/ps5/build-native.py`. [Platform build notes](platform/BUILD.md) give the dependencies and parameters for the Windows host build. The player preparation scripts are in `tools/player-setup`. They run directly from the separate Windows Setup Kit, which supplies their source tree, open-source converter binaries, and guest tools.
