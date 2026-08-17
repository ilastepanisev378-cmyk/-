# Seiko / Puzaty V11 QA

## Critical fixes
- Fixed `StirringMiniGame` lifecycle crash: `_stir_touch`, `_visual_event`, angle/timing fields now exist before `super().__init__()`.
- Fixed failed recipe/minigame transition crash caused by `on_leave -> cleanup`.
- Timing mini-game now deactivates its engine through the base `on_leave` lifecycle.
- Receipt popup creation is fail-safe; a popup exception falls back to the normal end-of-day path.
- Puzaty emotional states now remain visible longer: sad ~2.8s, purr ~2.0s.

## Gameplay
- Added fourth mini-game: precise pouring.
- Existing three mini-games remain: timing, stirring, ingredients.
- Recipe is not auto-selected: base/add-on are cleared at the start of every day.
- Failed minigame/recipe returns to the same day without advancing the story.
- Added more NPC quote variants selected by day/relationship.
- Renamed NPCs to Japanese-themed names: Aoi, Ren, Hina, Sora, Nao, Akira.
- Added staggered NPC arrival animation.
- Added more visible feedback in pouring/stirring.

## KV hygiene
- No `.5`, `.02`, `.1` style numeric literals in `ui.kv`.
- No multiline `pos_hint` declarations.
- No `Animation.then()` calls.
- No deprecated `allow_stretch` / `keep_ratio` properties.
- KV root callbacks statically match Python methods.

## Static checks
- `main.py`: AST parse OK.
- `managers.py`: AST parse OK.
- Required runtime assets present.
- ZIP integrity checked after packaging.

Kivy/SDL2 is not installed in the build environment, so native window interaction cannot be truthfully claimed here; final runtime validation should be done with the project's supplied Windows launcher.
