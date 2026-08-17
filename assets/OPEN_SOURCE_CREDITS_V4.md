# SEIKO / ПУЗАТЫЙ V4 — ASSET & LICENSE NOTES

## Runtime assets

The V4 runtime intentionally uses bundled local files only. No network connection is
required while the game is running.

### Pixel characters
The six NPC portraits in `assets/npc_*.png` are original procedural pixel-art assets
generated for this build. They are not copied from a third-party sprite sheet, so the
project can ship them without an external runtime dependency.

### Puzaty
The existing Puzaty cat images are kept from the supplied project.

### Audio
`lofi_night.wav`, `lofi_rain.wav` and `lofi_window.wav` are original procedural
ambient loops generated for this build. This avoids unknown licensing and MP3 codec
issues on mobile.

The supplied project's older MP3 tracks remain in `assets/`, but V4 does not put them
into the runtime playlist.

## Open-source references reviewed for future art replacement

These were checked specifically for compatible pixel/cozy assets:

- Pixel People — TokyoGeisha — CC0
  https://opengameart.org/content/pixel-people
- Pixel People Extras 01 — TokyoGeisha — CC0
  https://opengameart.org/content/pixel-people-extras-01
- Pixel People Extras 2 — TokyoGeisha — CC0
  https://opengameart.org/content/pixel-people-extras-2
- RPG character sprites — GrafxKid — CC0
  https://opengameart.org/content/rpg-character-sprites
- Basic 16x16 character sprites 4 directional — Bennyboi_hack — CC0
  https://opengameart.org/content/basic-16x16-character-sprites-4-directional
- Puny Characters — Shade — CC0
  https://opengameart.org/content/puny-characters
- Floor Tiles — GreyFrogGames — CC0
  https://opengameart.org/content/floor-tiles-0
- 4 Colour Interior Tileset — stealthix — CC0
  https://opengameart.org/content/4-colour-interior-tileset
- Lo-Fi and Chill Collection — Holizna — CC0
  https://opengameart.org/content/lo-fi-and-chill-collection
- lofi Compilation — TAD — CC0
  https://opengameart.org/content/lofi-compilation
- Interface Sounds — Kenney — CC0
  https://opengameart.org/content/interface-sounds
- Menu sounds — fvcalderan — CC0
  https://opengameart.org/content/menu-sounds

Important: the binary files from these external pages were not downloaded into V4
because the build environment could browse the source pages but could not fetch their
binary archives. V4 therefore uses self-contained replacements instead of pretending
that an external file was bundled.

## Design note

The relationship mechanics are written as communication/relationship choices, not as
a simulation or treatment model for any diagnosis. The game rewards listening,
asking, boundaries, pauses, repair after mistakes, and mutuality rather than trying to
"manage" another person's mental state.
