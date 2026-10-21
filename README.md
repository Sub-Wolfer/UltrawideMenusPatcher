# Ultrawide Menus Patcher

Source code of **Ultrawide Menus Patcher**, the optional tool for the Witcher 3 mod
**Ultrawide Menus** (21:9 and 32:9 inventory, shops, stash, blacksmith and reforge; on Nexus Mods).

Ultrawide Menus replaces three screen files: the inventory (also shop, loot container and stash),
the blacksmith and the reforge. Its main file is built from the game's own screens, so another mod
that replaces the same files (Gear Compare, Smooth UI Remastered, Recent Loot Tab, HoodSlots, UI
Remastered Edition, ...) loses its changes to them. For each screen the patcher takes the copy the
game would load without Ultrawide Menus, adds the ultrawide changes to it and saves the result in
Ultrawide Menus' own folder (`Mods\mod0000_UltrawideMenus\content`), so both mods' changes load
together.

What it does, and does not do:

- Reads the game's and your mods' bundle files, and writes only inside Ultrawide Menus' mod folder:
  `content\blob0.bundle`, `content\metadata.store` and `UltrawideMenusPatcher.txt`. A backup of the
  previous files goes to `Mods\mod0000_UltrawideMenus\patcher_backup\<date-time>`.
- Never changes the other mods' files and never redistributes them.
- A screen whose copy cannot be patched (or whose patched file fails the bytecode check,
  `avm2verify.py`) is left out of Ultrawide Menus' folder, so the other mod's file loads unchanged.
  The patcher says why.
- Stops while the game is running. No network access, no installer, no registry writes. It only
  *reads* the Steam/GOG registry keys to find the game folder.
- Python standard library only; no third-party packages.
- With Gear Compare Patcher: run Gear Compare Patcher first (1.1.2 or later skips Ultrawide Menus by
  itself), then this patcher.

## Files

| File | Purpose |
| --- | --- |
| `src/uw_patcher.py` | Command-line front end: finds the game and the mods, shows what it will do, writes the result |
| `src/uw_inv_patch.py` | Ultrawide changes to the inventory screen (Flash bytecode) |
| `src/uw_bs_patch.py` | Ultrawide changes to the blacksmith screen |
| `src/uw_tm_patch.py` | Ultrawide changes to the reforge screen |
| `src/uw_map_patch.py` | Shared helpers (this patcher never builds the world map) |
| `src/avm2verify.py` | Bytecode check run on every patched file |
| `src/abcrt.py` | ActionScript 3 (ABC) bytecode reader/writer |
| `src/cr2w.py` | CR2W wrapper of `.redswf` files |
| `src/w3bundle.py` | Witcher 3 `.bundle` reader/writer |
| `src/w3meta.py` | `metadata.store` writer |
| `src/lz4block.py` | LZ4 block decompression |

## Run from source

```
python src\uw_patcher.py
python src\uw_patcher.py --game "D:\Games\The Witcher 3" --yes
python src\uw_patcher.py --vanilla --yes
```

`--vanilla` builds from the game's own screens (the same files as the main file: undo).
`--dry-run` patches in memory and writes nothing.

## Build the exe

Windows, Python 3.10 (the release was built with Python 3.10 and PyInstaller 6.22.3):

```
build.bat
```

The exe is written to `dist\UltrawideMenusPatcher.exe`. PyInstaller builds are not byte-for-byte
reproducible, so a rebuilt exe will have a different hash.

Released exes (on Nexus Mods and GitHub Releases), SHA-256:

- 1.0.0: `1a91b93e3226359774aa4cb23411935ebb0704586544507213a8a425aa140766`

## License

MIT, see `LICENSE`.
