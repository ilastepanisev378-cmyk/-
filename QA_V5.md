# Seiko / Puzaty V5 QA

## Fixed in this pass
- Kivy KV `pos_hint` dictionaries are single-line and use leading-zero decimals.
- Removed a stale optional rain MP3 path.
- Added guarded menu navigation and settings/conversation popup calls.
- Hardened save-file sanitization for old/corrupt data.
- Minigame lifecycle now deactivates and cleans up on screen leave.
- Added a real `on_touch_down` start for the stirring minigame so touch movement is captured reliably on mobile.
- Ingredient minigame cup movement is calculated relative to the actual playfield, not the whole screen.
- Minigame finish has a safe fallback and logs the failing mode instead of leaving the game in a broken busy state.

## Static checks
- `main.py` and `managers.py`: `py_compile` OK.
- ZIP integrity: OK.
- No multiline `pos_hint` blocks remain.
- No bare `.5`, `.06`, `.045`, etc. numeric literals remain in KV.
- Root event callbacks referenced by KV were audited against Python methods.

## Runtime limitation
The build environment does not contain Kivy and has no network access, so a real SDL2/Kivy click-through test cannot be executed here. The code is hardened for the runtime paths most likely to fail, but final device testing still requires a machine with Kivy/Buildozer installed.
