# RingOut 1.0b source preview

Title ID PPSA99875. A PS5 tester confirmed that the Weapon Master mission Paradise of Altair loads with the corrected guest archive. Chapter 1 and guest costume switching still need confirmation on that revision.

The guest converter keeps the common archive within the GameCube buffer limit. If all portraits would exceed the limit, each guest uses their primary portrait for both costumes. The runtime rejects oversized older guest archives so the stock roster can still load.

Apply `weapon-master-fix.patch` to the pinned upstream checkout after the existing PS5 source changes. The incremental patch was checked against the pinned upstream revision and the source used for the console test. [Setup instructions](SETUP.md)

The publicly available material is a source preview. A store-installable build will require an executable that keeps original game code and data player-supplied.
