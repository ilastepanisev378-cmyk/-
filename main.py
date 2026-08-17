# -*- coding: utf-8 -*-
from __future__ import annotations

import math
import os
import random
import traceback

from kivy.config import Config

Config.set("graphics", "width", "360")
Config.set("graphics", "height", "640")
Config.set("kivy", "exit_on_escape", "0")
Config.set("kivy", "log_level", "warning")

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("KIVY_AUDIO", "sdl2")

from kivy.app import App
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.config import Config
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle
from kivy.lang import Builder
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.screenmanager import FadeTransition, Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.slider import Slider
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex

from managers import (
    AudioManager,
    CharacterManager,
    MinigameEngine,
    RecipeManager,
    ReceiptNarrativeManager,
    SaveManager,
    StoryManager,
    UIManager,
)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
SAVE_PATH = os.path.join(BASE_DIR, "save", "progress.json")


def asset(name: str) -> str:
    return os.path.join(ASSETS_DIR, name)


PALETTE = {
    "cream": get_color_from_hex("#FFF3D6"),
    "paper": get_color_from_hex("#F4E5C7"),
    "coffee": get_color_from_hex("#2A1A14"),
    "coffee2": get_color_from_hex("#3A241B"),
    "caramel": get_color_from_hex("#B97745"),
    "caramel2": get_color_from_hex("#D49A65"),
    "sage": get_color_from_hex("#819A78"),
    "rose": get_color_from_hex("#B87570"),
    "ink": get_color_from_hex("#2B211C"),
    "muted": get_color_from_hex("#D6BFA6"),
    "gold": get_color_from_hex("#E7C77A"),
}

PLAYLIST = [
    asset("lofi_night.wav"),
    asset("lofi_rain.wav"),
    asset("lofi_window.wav"),
]
RAIN_SOUND = None  # optional; gameplay never depends on an external rain asset
FONT = asset("WarmPixel.ttf") if os.path.isfile(asset("WarmPixel.ttf")) else "Roboto"


class RoundedPanel(BoxLayout):
    def __init__(self, bg="#2A1A14", alpha=0.88, radius=18, **kwargs):
        super().__init__(**kwargs)
        self.bg = get_color_from_hex(bg)
        self.alpha = alpha
        self._radius = radius
        with self.canvas.before:
            self._color = Color(*self.bg[:3], alpha)
            self._rect = RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[radius],
            )
        self.bind(pos=self._sync_canvas, size=self._sync_canvas)

    def _sync_canvas(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size


class PressButton(Button):
    def __init__(self, **kwargs):
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_down", "")
        kwargs.setdefault("background_color", PALETTE["caramel"])
        kwargs.setdefault("color", PALETTE["cream"])
        kwargs.setdefault("font_name", FONT)
        kwargs.setdefault("font_size", 14)
        super().__init__(**kwargs)
        self.bind(on_press=self._on_press, on_release=self._on_release)

    def _on_press(self, *_):
        app = App.get_running_app()
        if app:
            app.audio.play_sfx("ui_click.wav")
            if app.ui.enabled:
                Animation(opacity=0.72, duration=0.05).start(self)

    def _on_release(self, *_):
        app = App.get_running_app()
        if app and app.ui.enabled:
            Animation(opacity=1, duration=0.08).start(self)


class TypewriterLabel(Label):
    full_text = StringProperty("")
    typing = BooleanProperty(False)
    char_delay = NumericProperty(0.025)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.font_name = FONT
        self._event = None
        self._generation = 0

    def type_text(self, text, speed=None):
        self._generation += 1
        generation = self._generation
        self.full_text = str(text)
        self.text = ""
        self.typing = True
        self._index = 0

        if speed is not None:
            self.char_delay = max(0.008, float(speed))

        if self._event:
            self._event.cancel()
            self._event = None

        app = App.get_running_app()
        if not app or not app.save.data["settings"].get("typewriter", True):
            self.text = self.full_text
            self.typing = False
            return

        def step(dt):
            if generation != self._generation:
                return False
            return self._step(dt)

        self._event = Clock.schedule_interval(step, self.char_delay)

    def _step(self, _dt):
        if self._index >= len(self.full_text):
            self.typing = False
            if self._event:
                self._event.cancel()
                self._event = None
            return False

        ch = self.full_text[self._index]
        self.text += ch
        self._index += 1

        if ch.strip() and self._index % 3 == 0:
            app = App.get_running_app()
            if app:
                app.audio.play_sfx("typewriter.wav")
        return True

    def skip(self):
        if not self.typing:
            return
        self._generation += 1
        if self._event:
            self._event.cancel()
            self._event = None
        self.text = self.full_text
        self.typing = False

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos) and self.typing:
            self.skip()
            return True
        return super().on_touch_down(touch)


class AnimatedScreen(Screen):
    def on_enter(self, *_):
        app = App.get_running_app()
        duration = 0.22 if app and app.ui.enabled else 0
        self.opacity = 0
        Animation(opacity=1, duration=duration).start(self)


class Atmosphere(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._time = 0.0
        self._drops = [
            (random.random(), random.random(), random.uniform(0.8, 2.0))
            for _ in range(24)
        ]
        self._event = Clock.schedule_interval(self._tick, 1 / 24)
        self.bind(pos=self._draw, size=self._draw)

    def _tick(self, dt):
        self._time += min(dt, 0.08)
        self._draw()

    def _draw(self, *_):
        self.canvas.after.clear()
        with self.canvas.after:
            Color(0.75, 0.82, 0.90, 0.10)
            for x, y, speed in self._drops:
                yy = (y - self._time * speed * 0.055) % 1.0
                x0 = self.x + x * self.width
                y0 = self.y + yy * self.height
                Line(points=(x0, y0, x0 - 2, y0 - 9), width=1)

            pulse = 0.03 + 0.008 * math.sin(self._time * 1.2)
            Color(0.95, 0.72, 0.42, pulse)
            Ellipse(
                pos=(self.x + self.width * 0.02, self.y + self.height * 0.38),
                size=(self.width * 0.42, self.height * 0.42),
            )

    def stop(self):
        if self._event:
            self._event.cancel()
            self._event = None


class NPCWidget(ButtonBehavior, Image):
    npc_name = StringProperty("")


class NewGamePopup(Popup):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = "НОВАЯ ИГРА"
        self.size_hint = (0.88, 0.42)
        self.auto_dismiss = True
        self.background_color = (0, 0, 0, 0)

        box = BoxLayout(
            orientation="vertical",
            padding=14,
            spacing=9,
        )
        box.add_widget(
            Label(
                text="Начать историю заново?\nСтарый прогресс будет заменён.",
                font_name=FONT,
                color=PALETTE["cream"],
                halign="center",
            )
        )
        row = BoxLayout(spacing=8, size_hint_y=None, height=48)
        cancel = PressButton(text="ОТМЕНА", background_color=PALETTE["coffee2"])
        confirm = PressButton(text="НАЧАТЬ", background_color=PALETTE["rose"])
        row.add_widget(cancel)
        row.add_widget(confirm)
        box.add_widget(row)
        self.content = box
        cancel.bind(on_release=lambda *_: self.dismiss())
        confirm.bind(on_release=lambda *_: self.confirm())

    def confirm(self):
        app = App.get_running_app()
        app.save.reset()
        app.audio.configure(app.save.data["settings"])
        self.dismiss()
        app.sm.current = "menu"


class ChoicePopup(Popup):
    def __init__(self, owner, **kwargs):
        super().__init__(**kwargs)
        self.owner_screen = owner
        self.title = "НЕБОЛЬШОЙ РАЗГОВОР"
        self.size_hint = (0.92, 0.70)
        self.auto_dismiss = False
        self.background_color = (0, 0, 0, 0)

        box = BoxLayout(
            orientation="vertical",
            padding=12,
            spacing=8,
        )
        prompt = Label(
            text="Что ответить Пузатому?",
            font_name=FONT,
            font_size=16,
            color=PALETTE["cream"],
            size_hint_y=None,
            height=46,
        )
        box.add_widget(prompt)

        choices = owner.story.choices(owner.day) or ()
        for text, delta, reason in choices:
            button = PressButton(
                text=text,
                background_color=PALETTE["coffee2"],
                size_hint_y=None,
                height=52,
            )
            button.bind(
                on_release=lambda _btn, d=delta, r=reason: self.choose(d, r)
            )
            box.add_widget(button)

        cancel = PressButton(
            text="ПОЗЖЕ",
            background_color=PALETTE["sage"],
            size_hint_y=None,
            height=44,
        )
        cancel.bind(on_release=lambda *_: self.dismiss())
        box.add_widget(cancel)
        self.content = box

    def choose(self, delta, reason):
        app = App.get_running_app()
        app.save.data["flags"]["last_choice_day"] = self.owner_screen.day
        relationship = app.save.add_relationship(delta, reason)
        self.owner_screen.relationship = relationship
        self.owner_screen.ids.relationship.text = f"СВЯЗЬ {relationship:+d}"
        character = self.owner_screen._ensure_character()
        character.perfect() if delta > 0 else character.surprise()
        self.owner_screen.ids.dialogue.type_text(reason, 0.012)
        self.dismiss()


class MainMenu(AnimatedScreen):
    def on_enter(self, *_):
        super().on_enter()
        app = App.get_running_app()
        day = int(app.save.data.get("day", 1))
        relationship = int(app.save.data.get("relationship", 0))
        self.ids.day_text.text = f"День {day} / 14  •  связь {relationship:+d}"

        for index, child in enumerate(reversed(self.ids.menu_box.children)):
            app.ui.fade_in(child, 0.18, index * 0.045)

    def start_game(self):
        try:
            app = App.get_running_app()
            app.sm.current = "coffee"
        except Exception:
            self._safe_menu_error("Не удалось открыть кофейню.")

    def open_diary(self):
        try:
            App.get_running_app().sm.current = "diary"
        except Exception:
            self._safe_menu_error("Не удалось открыть дневник.")

    def open_settings(self):
        try:
            SettingsPopup().open()
        except Exception:
            self._safe_menu_error("Настройки временно недоступны.")

    def new_game(self):
        try:
            NewGamePopup().open()
        except Exception:
            self._safe_menu_error("Не удалось открыть окно новой игры.")

    def _safe_menu_error(self, text):
        try:
            app = App.get_running_app()
            if app and hasattr(app, "audio"):
                app.audio.play_sfx("mistake.wav")
        except Exception:
            pass


class PuzatyWidget(ButtonBehavior, Image):
    pass


class TimingTrack(Widget):
    cursor_value = NumericProperty(0)
    target_start = NumericProperty(70)
    target_end = NumericProperty(88)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(
            pos=self._redraw,
            size=self._redraw,
            cursor_value=self._redraw,
            target_start=self._redraw,
            target_end=self._redraw,
        )
        self._redraw()

    def _redraw(self, *_):
        self.canvas.clear()
        with self.canvas:
            Color(0.16, 0.11, 0.09, 0.95)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[14])
            x1 = self.x + self.width * self.target_start / 100.0
            x2 = self.x + self.width * self.target_end / 100.0
            Color(0.38, 0.68, 0.42, 1)
            RoundedRectangle(
                pos=(x1, self.y + 4),
                size=(max(2, x2 - x1), max(2, self.height - 8)),
                radius=[10],
            )
            cx = self.x + self.width * self.cursor_value / 100.0
            Color(1, 0.87, 0.55, 1)
            RoundedRectangle(
                pos=(cx - 4, self.y + 1),
                size=(8, max(2, self.height - 2)),
                radius=[4],
            )


class _NullCharacter:
    """Fail-safe character controller: gameplay must continue if an asset/widget fails."""

    def start_idle_breath(self):
        return None

    def stop(self):
        return None

    def set_state(self, *_args, **_kwargs):
        return None

    def surprise(self):
        return None

    def perfect(self):
        return None

    def mistake(self):
        return None

    def purr(self):
        return None


class CoffeeShop(AnimatedScreen):
    day = NumericProperty(1)
    base = StringProperty("Травяной чай")
    addon = StringProperty("Ягоды")
    temperature = NumericProperty(80)
    target_text = StringProperty("")
    busy = BooleanProperty(False)
    relationship = NumericProperty(0)

    def __init__(self, **kwargs):
        # Kivy dispatches on_kv_post during Widget.__init__. Therefore every
        # attribute touched by on_kv_post MUST exist before super().__init__().
        self.recipe_manager = RecipeManager()
        self.story = StoryManager()
        self.receipts = ReceiptNarrativeManager()
        self.minigame = None
        self._temp_event = None
        self._brew_generation = 0
        self.character = None
        self._character_bound = False
        self.atmosphere = None
        super().__init__(**kwargs)

    def _ensure_character(self):
        """Lazily create the character controller and never let a missing controller crash gameplay."""
        if self.character is not None:
            return self.character
        try:
            app = App.get_running_app()
            widget = self.ids.get("puzaty")
            if widget is None or app is None:
                raise RuntimeError("Puzaty widget is not ready")
            self.character = CharacterManager(widget, asset, app.ui, app.audio)
            self.character.start_idle_breath()
            if not self._character_bound:
                widget.bind(on_release=self.on_puzaty_click)
                self._character_bound = True
            return self.character
        except Exception:
            self._log_error("ensure_character")
            self.character = _NullCharacter()
            return self.character

    def on_kv_post(self, *_):
        self._ensure_character()
        try:
            self.atmosphere = next(
                (widget for widget in self.ids.guest_area.children if isinstance(widget, Atmosphere)),
                None,
            )
        except Exception:
            self.atmosphere = None

    def on_enter(self, *_):
        super().on_enter()
        self._ensure_character()
        self.enter_day()

    def on_leave(self, *_):
        self._stop_temperature()

    def enter_day(self):
        app = App.get_running_app()
        self._stop_temperature()
        self.busy = False
        self.minigame = None

        self.day = max(1, min(14, int(app.save.data.get("day", 1))))
        self.relationship = int(app.save.data.get("relationship", 0))
        recipe = self.recipe_manager.recipe_for_day(self.day)

        # Do not auto-select the correct recipe. The player must compose it.
        self.base = ""
        self.addon = ""
        self.target_text = (
            f"Температура: {recipe.target_temp[0]}–{recipe.target_temp[1]}°C"
        )
        self.ids.day_label.text = f"ДЕНЬ {self.day} / 14"
        self.ids.weather_label.text = self.story.weather(self.day)
        self.ids.relationship.text = f"СВЯЗЬ {self.relationship:+d}"
        self.ids.recipe_hint.text = (
            f"{recipe.description}\n"
            "Собери напиток сам: выбери основу и добавку. "
            "Подсказки можно получить у посетителей."
        )
        self.ids.dialogue.type_text(self.story.intro(self.day), 0.016)
        self._start_temperature()
        self._animate_guest_arrival()
        self._update_npcs()
        self._animate_npc_arrival()

    def _update_npcs(self):
        names = ["lena", "max", "ira", "noah", "mira", "dan"]
        offset = (self.day - 1) % len(names)
        selected = names[offset:] + names[:offset]
        for widget, name in zip(
            [self.ids.npc1, self.ids.npc2, self.ids.npc3],
            selected[:3],
        ):
            widget.npc_name = name
            widget.source = asset(f"npc_{name}_0.png")
            widget.reload()

    def _animate_npc_arrival(self):
        app = App.get_running_app()
        if not app or not app.ui.enabled:
            return
        for index, widget in enumerate((self.ids.npc1, self.ids.npc2, self.ids.npc3)):
            widget.opacity = 0
            target_y = widget.y
            widget.y = target_y - 18
            Clock.schedule_once(
                lambda _dt, w=widget, y=target_y: Animation(
                    y=y, opacity=1, duration=0.26, t="out_back"
                ).start(w),
                index * 0.08,
            )

    def on_npc_click(self, name):
        app = App.get_running_app()
        label, quote = self.story.npc_quote(name, self.day, self.relationship)
        app.save.data["flags"]["npc_clicks"] = int(
            app.save.data["flags"].get("npc_clicks", 0)
        ) + 1
        app.save.save()
        self.ids.dialogue.type_text(f"{label}: {quote}", 0.012)
        app.ui.pulse(self.ids.dialogue_card)
        for widget in (self.ids.npc1, self.ids.npc2, self.ids.npc3):
            if widget.npc_name == name:
                Animation(size=(widget.width * 1.08, widget.height * 1.08), duration=0.10, t="out_back").start(widget)
                Clock.schedule_once(lambda _dt, w=widget: Animation(size=(w.width / 1.08, w.height / 1.08), duration=0.16).start(w), 0.10)
                break

    def open_settings(self):
        try:
            SettingsPopup().open()
        except Exception:
            self.ids.dialogue.type_text("«Настройки пока не отвечают. Продолжим без них»." , 0.012)

    def open_conversation(self):
        app = App.get_running_app()
        if app.save.data["flags"].get("last_choice_day") == self.day:
            self.ids.dialogue.type_text(
                "«Мы уже поговорили сегодня. Можно просто побыть здесь».",
                0.014,
            )
            return
        try:
            ChoicePopup(self).open()
        except Exception:
            self.ids.dialogue.type_text("«Похоже, разговор застрял. Давай просто побудем здесь»." , 0.012)

    def on_puzaty_click(self, *_):
        self._ensure_character().purr()
        self.ids.dialogue.type_text(
            random.choice(
                [
                    "«Мр-р. Ещё раз, пожалуйста».",
                    "«Вот так лучше».",
                    "«Сегодня можно чуть-чуть тишины?»",
                    "«Если я вернусь, это будет считаться привычкой?»",
                    "«Ты опять смотришь на температуру, а не на меня».",
                    "«Только не рассказывай, что я скучал».",
                    "«Мр-р... кажется, вечер удался».",
                ]
            ),
            0.012,
        )

    def _animate_guest_arrival(self):
        widget = self.ids.puzaty
        if not App.get_running_app().ui.enabled:
            return
        target = widget.x
        widget.x = self.width + 100
        Animation(x=target, duration=0.52, t="out_cubic").start(widget)

    def _start_temperature(self):
        self._stop_temperature()
        phase = [0.0]

        def tick(dt):
            if self.busy:
                return
            phase[0] += min(dt, 0.08) * 1.35
            self.temperature = 76 + (math.sin(phase[0]) + 1) * 12
            self.ids.temp_value.text = f"{int(self.temperature)}°C"
            self.ids.temp_bar.value = self.temperature

        self._temp_event = Clock.schedule_interval(tick, 1 / 18)

    def _stop_temperature(self):
        if self._temp_event:
            self._temp_event.cancel()
            self._temp_event = None

    def select_base(self, text):
        if self.busy:
            return
        self.base = text
        self._choice_feedback()

    def select_addon(self, text):
        if self.busy:
            return
        self.addon = text
        self._choice_feedback()

    def _choice_feedback(self):
        if self.character:
            self.character.surprise()
        self.ids.dialogue.type_text(
            random.choice(
                [
                    "Пузатый следит за выбором. «Хорошо. Только не торопись».",
                    "«Запах уже меняется». Пузатый приподнимает ухо.",
                    "«Интересно, что из этого получится?»",
                ]
            ),
            0.012,
        )

    def start_brew(self):
        if self.busy:
            return
        if not self.base or not self.addon:
            self.ids.dialogue.type_text(
                "«Сначала выбери основу и добавку. Я не хочу угадывать за тебя». ",
                0.012,
            )
            self._ensure_character().surprise()
            return
        try:
            self.busy = True
            self._stop_temperature()
            self._brew_generation += 1
            generation = self._brew_generation
            self._choice_feedback()
            self.ids.dialogue.type_text("«Теперь главное — не спешить».", 0.014)

            app = App.get_running_app()
            self.minigame = MinigameEngine(self, app.audio)
            self.minigame.start()
            screen_name = f"minigame_{self.minigame.mode}"
            screen = app.minigame_screens[self.minigame.mode]
            app.sm.current = screen_name
            screen.start_game(self, generation)
        except Exception:
            self.busy = False
            self._log_error("start_brew")
            app = App.get_running_app()
            app.sm.current = "coffee"
            self._start_temperature()
            self.ids.dialogue.type_text(
                "«Стоп. Что-то заклинило. Давай попробуем ещё раз».",
                0.012,
            )

    def finish_brew(self, skill_score, final_temp=None, generation=None):
        if generation is not None and generation != self._brew_generation:
            return
        if not self.busy:
            return

        self.busy = False
        temp = float(final_temp if final_temp is not None else self.temperature)
        result = self.recipe_manager.evaluate(
            self.day,
            self.base,
            self.addon,
            temp,
            skill_score,
        )
        app = App.get_running_app()
        app.save.record_brew(
            self.day,
            self.base,
            self.addon,
            result.quality,
            result.score,
        )
        self.relationship = int(app.save.data["relationship"])
        self.ids.relationship.text = f"СВЯЗЬ {self.relationship:+d}"

        character = self._ensure_character()
        if result.quality == "perfect":
            character.perfect()
        elif result.quality == "good":
            character.set_state("idle", 0.4)
        else:
            character.mistake()

        self.ids.dialogue.type_text(
            self.story.ending(self.day, result.quality, self.relationship),
            0.012,
        )

        note = self.receipts.get(
            self.day,
            result.quality,
            app.save.data["history"],
            self.relationship,
        )
        try:
            ReceiptPopup(note, result, self._after_receipt).open()
        except Exception:
            self._log_error("receipt_popup")
            self._after_receipt(note, result.quality)

    def _after_receipt(self, note, quality):
        app = App.get_running_app()
        app.save.add_diary(f"День {self.day} • {quality}\n{note}")

        # A failed drink is a real outcome, but never blocks or skips the story.
        # The player stays on the same day and can rebuild the drink.
        if quality == "bad":
            self.busy = False
            self.minigame = None
            self.ids.dialogue.type_text(
                "«Не получилось. Ничего страшного — этот вечер ещё можно переписать. Попробуем снова?»",
                0.012,
            )
            self._start_temperature()
            app.save.save()
            return

        if self.day < 14:
            app.save.data["day"] = self.day + 1
            app.save.save()
            Clock.schedule_once(lambda _dt: self.enter_day(), 0.12)
        else:
            app.save.save()
            self.ids.dialogue.type_text(
                "Пузатый задерживается у двери. «До завтра, бариста».",
                0.014,
            )
            self._start_temperature()

    def _log_error(self, where):
        try:
            path = os.path.join(
                os.environ.get("TEMP", BASE_DIR),
                "Seiko_Puzaty_runtime_error.txt",
            )
            with open(path, "a", encoding="utf-8") as log:
                log.write(f"\n--- {where} ---\n")
                traceback.print_exc(file=log)
        except OSError:
            pass

    def back(self):
        self.busy = False
        self._stop_temperature()
        if self.minigame:
            self.minigame.active = False
        App.get_running_app().sm.current = "menu"


class MiniGameBase(AnimatedScreen):
    mode_name = StringProperty("")

    def __init__(self, **kwargs):
        # Attributes must exist before any Kivy lifecycle callback can reach cleanup().
        self.owner = None
        self.engine = None
        self.generation = None
        super().__init__(**kwargs)

        self.engine = None
        self.generation = None

    def start_game(self, owner, generation=None):
        self.owner = owner
        self.engine = owner.minigame
        self.generation = generation
        names = {
            "timing": "ТАЙМИНГ-БАЛАНС",
            "stirring": "ИДЕАЛЬНОЕ РАЗМЕШИВАНИЕ",
            "ingredients": "СБОР ИНГРЕДИЕНТОВ",
            "pouring": "ТОЧНЫЙ НАЛИВ",
        }
        self.mode_name = names.get(self.engine.mode, "МИНИ-ИГРА")
        self.ids.mode_title.text = self.mode_name
        self.reset_mode()
        owner._ensure_character().surprise()
        App.get_running_app().ui.fade_in(self.ids.game_card, 0.20)

    def reset_mode(self):
        pass

    def finish(self, score, temp=None):
        if not self.owner or not self.engine or not self.engine.active:
            return
        owner = self.owner
        app = App.get_running_app()
        try:
            final_score = max(0.0, min(1.0, float(score)))
            if final_score < 0.45:
                self.fail(final_score)
                return
            final_score = self.engine.finish(final_score)
            owner.finish_brew(final_score, temp, self.generation)
        except Exception:
            self.engine.active = False
            owner.busy = False
            owner._start_temperature()
            owner._log_error(f"minigame_finish:{self.engine.mode}")
            try:
                owner.ids.dialogue.type_text("«Мини-игра споткнулась. Ничего страшного — попробуем ещё раз»." , 0.012)
            except Exception:
                pass
        finally:
            self.cleanup()
            try:
                app.sm.current = "coffee"
            except Exception:
                pass

    def fail(self, score=0.0):
        """Lose the current minigame without advancing the story/day."""
        if not self.owner or not self.engine or not self.engine.active:
            return
        owner = self.owner
        app = App.get_running_app()
        self.engine.finish(score)
        owner.busy = False
        owner._start_temperature()
        try:
            app.audio.play_sfx("mistake.wav")
        except Exception:
            pass
        try:
            owner._ensure_character().mistake()
            owner.ids.dialogue.type_text(
                "«Не вышло. Ничего страшного — смена не закончилась. Попробуем ещё раз?»",
                0.012,
            )
        except Exception:
            pass
        self.cleanup()
        try:
            app.sm.current = "coffee"
        except Exception:
            pass

    def on_leave(self, *_):
        if self.engine:
            self.engine.active = False
        self.cleanup()

    def cancel_game(self):
        if self.engine:
            self.engine.active = False
        if self.owner:
            self.owner.busy = False
            self.owner._start_temperature()
        self.cleanup()
        App.get_running_app().sm.current = "coffee"

    def cleanup(self):
        pass


class TimingMiniGame(MiniGameBase):
    cursor = NumericProperty(0)
    target_start = NumericProperty(70)
    target_end = NumericProperty(88)

    def reset_mode(self):
        self.cleanup()
        self.cursor = 0
        self._event = Clock.schedule_interval(self._tick, 1 / 30)

    def _tick(self, dt):
        if not self.engine or not self.engine.active:
            return
        self.cursor = (self.cursor + min(dt, 0.06) * 92) % 100
        self.ids.timing_cursor.cursor_value = self.cursor

    def hit(self):
        if not self.engine or not self.engine.active:
            return
        self.cleanup()
        center = (self.target_start + self.target_end) / 2
        width = self.target_end - self.target_start
        score = self.engine.timing_score(self.cursor, center, width)
        temp = 76 + self.cursor * 0.20
        App.get_running_app().audio.play_sfx("ui_click.wav")
        self.finish(score, temp)

    def cleanup(self):
        event = getattr(self, "_event", None)
        if event:
            event.cancel()
            self._event = None

    def on_leave(self, *_):
        super().on_leave()


class StirringMiniGame(MiniGameBase):
    revolutions = NumericProperty(0)
    stir_angle = NumericProperty(0)
    rhythm_value = NumericProperty(0)
    rhythm_text = StringProperty("НАЧНИ КРУТИТЬ")
    progress_value = NumericProperty(0)
    speed_text = StringProperty("Кругов: 0.0")

    def __init__(self, **kwargs):
        # ScreenManager may call cleanup() before reset_mode() on the first leave.
        self._stir_touch = None
        self._visual_event = None
        self._last_angle = None
        self._last_t = None
        self._visual_phase = 0.0
        self._accum = 0.0
        self._speeds = []
        super().__init__(**kwargs)

    def reset_mode(self):
        self.cleanup()
        self.revolutions = 0
        self.progress_value = 0
        self.rhythm_value = 0
        self.rhythm_text = "НАЧНИ КРУТИТЬ"
        self.stir_angle = 0
        self._visual_phase = 0.0
        self._accum = 0.0
        self._last_angle = None
        self._last_t = None
        self._speeds = []
        self._stir_touch = None
        self._visual_event = Clock.schedule_interval(self._animate_stir_visual, 1 / 30)
        self._draw_ring()

    def _animate_stir_visual(self, dt):
        if not self.engine or not self.engine.active:
            return
        self._visual_phase += min(dt, 0.06) * 1.8
        if self._stir_touch is None:
            self.stir_angle = (self._visual_phase * 0.65) % (2 * math.pi)
        self._draw_ring()

    def _rhythm_state(self, speed):
        target = 5.5
        error = abs(speed - target)
        self.rhythm_value = max(0.0, min(1.0, 1.0 - error / target))
        if speed < 3.4:
            self.rhythm_text = "СЛИШКОМ МЕДЛЕННО"
        elif speed > 7.6:
            self.rhythm_text = "СЛИШКОМ БЫСТРО"
        else:
            self.rhythm_text = "ИДЕАЛЬНЫЙ РИТМ"

    def _draw_ring(self):
        if "stir_ring" not in self.ids:
            return
        ring = self.ids.stir_ring
        ring.canvas.after.clear()
        radius = min(ring.width, ring.height) * 0.34
        cx, cy = ring.center_x, ring.center_y
        angle = self.stir_angle
        spoon_len = radius * 0.82
        sx = cx + math.cos(angle) * spoon_len
        sy = cy + math.sin(angle) * spoon_len
        # Outer ring + inner target track + animated spoon + center pulse.
        if self.rhythm_text == "ИДЕАЛЬНЫЙ РИТМ":
            ring_color = (0.38, 0.72, 0.48, 1)
        elif self.rhythm_text == "СЛИШКОМ БЫСТРО":
            ring_color = (0.82, 0.40, 0.34, 1)
        elif self.rhythm_text == "СЛИШКОМ МЕДЛЕННО":
            ring_color = (0.80, 0.58, 0.30, 1)
        else:
            ring_color = (0.83, 0.66, 0.45, 0.85)
        with ring.canvas.after:
            Color(*ring_color)
            Line(circle=(cx, cy, radius), width=3.0)
            Color(0.95, 0.82, 0.52, 0.28)
            Line(circle=(cx, cy, radius * 0.63), width=1.2)
            Color(0.95, 0.82, 0.52, 0.92)
            Line(points=(cx, cy, sx, sy), width=4.0)
            Ellipse(pos=(sx - 7, sy - 7), size=(14, 14))
            pulse = 8 + 3 * math.sin(self._visual_phase * 3.0)
            Color(*ring_color)
            Ellipse(pos=(cx - pulse / 2, cy - pulse / 2), size=(pulse, pulse))

    def on_touch_down(self, touch):
        ring = self.ids.stir_ring
        if ring.collide_point(*touch.pos):
            self._stir_touch = touch
            touch.grab(self)
            self._last_angle = math.atan2(touch.y - ring.center_y, touch.x - ring.center_x)
            self._last_t = Clock.get_time()
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if self._stir_touch is not touch:
            return super().on_touch_move(touch)

        ring = self.ids.stir_ring
        dx = touch.x - ring.center_x
        dy = touch.y - ring.center_y
        angle = math.atan2(dy, dx)

        self.stir_angle = angle
        if self._last_angle is not None:
            delta = angle - self._last_angle
            if delta > math.pi:
                delta -= 2 * math.pi
            elif delta < -math.pi:
                delta += 2 * math.pi

            self._accum += abs(delta)
            self.revolutions = self._accum / (2 * math.pi)
            now = Clock.get_time()
            if self._last_t is not None:
                speed = abs(delta) / max(0.02, now - self._last_t)
                self._speeds.append(speed)
                self._rhythm_state(speed)
            self._last_t = now
            self.progress_value = min(1.0, self.revolutions / 2.2)
            self.speed_text = f"Кругов: {self.revolutions:.1f} / 2.2"

        self._last_angle = angle
        return True

    def on_touch_up(self, touch):
        if self._stir_touch is touch:
            try:
                touch.ungrab(self)
            except Exception:
                pass
            self._stir_touch = None
            self._last_angle = None
            self._last_t = None
            return True
        return super().on_touch_up(touch)

    def finish_stir(self):
        if not self.engine or not self.engine.active:
            return
        avg = sum(self._speeds[-40:]) / max(1, len(self._speeds[-40:]))
        score = self.engine.stirring_score(self.revolutions, avg, 5.5)
        self.finish(score, 80 + score * 7)

    def cleanup(self):
        event = getattr(self, "_visual_event", None)
        if event:
            event.cancel()
            self._visual_event = None
        touch = getattr(self, "_stir_touch", None)
        if touch is not None:
            try:
                touch.ungrab(self)
            except Exception:
                pass
        self._stir_touch = None
        self._last_angle = None
        self._last_t = None


class PouringMiniGame(MiniGameBase):
    fill_value = NumericProperty(0)
    target_start = NumericProperty(58)
    target_end = NumericProperty(72)
    direction = NumericProperty(1)

    def __init__(self, **kwargs):
        self._event = None
        self._phase = 0.0
        super().__init__(**kwargs)

    def reset_mode(self):
        self.cleanup()
        self.fill_value = 12
        self._phase = random.uniform(0, math.pi)
        self.direction = 1
        self._event = Clock.schedule_interval(self._tick, 1 / 30)
        self._update_visuals()

    def _tick(self, dt):
        if not self.engine or not self.engine.active:
            return
        self._phase += min(dt, 0.06) * 1.9
        # A smooth back-and-forth pour meter.
        self.fill_value = 50 + 44 * math.sin(self._phase)
        self._update_visuals()

    def _update_visuals(self):
        if "pour_bar" in self.ids:
            self.ids.pour_bar.value = self.fill_value
        if "pour_value" in self.ids:
            self.ids.pour_value.text = f"{int(self.fill_value)}%"
        if "pour_hint" in self.ids:
            if self.target_start <= self.fill_value <= self.target_end:
                self.ids.pour_hint.text = "ИДЕАЛЬНО — ОСТАНОВИ!"
            elif self.fill_value < self.target_start:
                self.ids.pour_hint.text = "ЕЩЁ НЕМНОГО..."
            else:
                self.ids.pour_hint.text = "СТОП! НЕ ПЕРЕЛЕЙ"

    def stop_pour(self):
        if not self.engine or not self.engine.active:
            return
        score = self.engine.pouring_score(
            self.fill_value, self.target_start, self.target_end,
        )
        self.cleanup()
        App.get_running_app().audio.play_sfx("ui_click.wav")
        self.finish(score, 74 + score * 18)

    def cleanup(self):
        event = getattr(self, "_event", None)
        if event:
            event.cancel()
            self._event = None


class IngredientMiniGame(MiniGameBase):
    cup_x = NumericProperty(0.5)
    elapsed = NumericProperty(0)

    def reset_mode(self):
        self.cleanup()
        self.elapsed = 0
        self.caught_good = 0
        self.missed_good = 0
        self.caught_bad = 0
        self.items = []
        self._spawn_clock = Clock.schedule_interval(self._spawn_item, 0.42)
        self._fall_clock = Clock.schedule_interval(self._fall, 1 / 30)

    def _spawn_item(self, _dt):
        if not self.engine or not self.engine.active:
            return

        desired = self.owner.addon
        choices = [
            (desired, True),
            ("Соль", False),
            ("Лёд", False),
            ("Корица", desired == "Корица"),
            ("Мёд", desired == "Мёд"),
            ("Мята", desired == "Мята"),
            ("Ягоды", desired == "Ягоды"),
        ]
        kind, good = random.choice(choices)
        label = Label(
            text=kind,
            font_name=FONT,
            font_size=10,
            color=PALETTE["cream"],
            size_hint=(None, None),
            size=(74, 30),
        )
        area = self.ids.falling
        max_x = max(area.x + 8, area.right - label.width - 8)
        label.pos = (
            random.uniform(area.x + 8, max_x),
            area.top - label.height - 4,
        )
        area.add_widget(label)
        self.items.append((label, good))

    def _fall(self, dt):
        if not self.engine or not self.engine.active:
            return
        self.elapsed += min(dt, 0.1)

        cup = self.ids.cup
        speed = min(7.0, 3.8 + dt * 20)
        for label, good in list(self.items):
            label.y -= speed
            caught = (
                label.y <= cup.top
                and label.y + label.height >= cup.y
                and abs(label.center_x - cup.center_x) < 48
            )
            if caught:
                if good:
                    self.caught_good += 1
                else:
                    self.caught_bad += 1
                self._remove_item(label, good)
            elif label.top < self.ids.falling.y:
                if good:
                    self.missed_good += 1
                self._remove_item(label, good)

        self.ids.score_text.text = (
            f"Поймано: {self.caught_good}  •  Ошибок: {self.caught_bad}"
        )

    def _remove_item(self, label, good):
        try:
            if label.parent:
                label.parent.remove_widget(label)
        except Exception:
            pass
        try:
            self.items.remove((label, good))
        except ValueError:
            pass

    def on_touch_down(self, touch):
        if self.ids.falling.collide_point(*touch.pos):
            area = self.ids.falling
            normalized = (touch.x - area.x) / max(1.0, area.width)
            self.move_cup(normalized)
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if self.ids.falling.collide_point(*touch.pos):
            area = self.ids.falling
            normalized = (touch.x - area.x) / max(1.0, area.width)
            self.move_cup(normalized)
            return True
        return super().on_touch_move(touch)

    def move_cup(self, normalized_x):
        self.cup_x = max(0.08, min(0.92, float(normalized_x)))
        self.ids.cup.pos_hint = {"center_x": self.cup_x}

    def finish_ingredients(self):
        if not self.engine or not self.engine.active:
            return
        if self.elapsed < 3.0:
            self.ids.score_text.text = "Ещё немного — собери ингредиенты"
            return
        score = self.engine.ingredient_score(
            self.caught_good,
            self.missed_good,
            self.caught_bad,
        )
        self.finish(score, 76 + score * 12)

    def cleanup(self):
        for attr in ("_spawn_clock", "_fall_clock"):
            event = getattr(self, attr, None)
            if event:
                event.cancel()
                setattr(self, attr, None)

        for label, _good in list(getattr(self, "items", [])):
            try:
                if label.parent:
                    label.parent.remove_widget(label)
            except Exception:
                pass
        self.items = []


class ReceiptPopup(Popup):
    def __init__(self, note, result, on_saved, **kwargs):
        super().__init__(**kwargs)
        self.note = note
        self.result = result
        self.on_saved = on_saved
        self.title = "ТЕРМОЧЕК"
        self.auto_dismiss = False
        self.size_hint = (0.88, 0.82)
        self.background_color = (0, 0, 0, 0)
        self._lines = [
            "      СЕЙКО / 58 mm",
            "------------------------------",
            result.recipe.name,
            f"Оценка: {self._quality_ru(result.quality)}",
            f"Рецепт: {int(result.recipe_match * 100)}%",
            f"Навык: {int(result.skill_score * 100)}%",
            "------------------------------",
        ] + note.split("\n") + [
            "------------------------------",
            "Пусть тёплое остаётся тёплым.",
        ]
        self._index = 0
        self._printer_event = None

    def on_open(self):
        super().on_open()
        app = App.get_running_app()
        self.opacity = 0
        self.ids.receipt_text.text = ""
        self.ids.save_btn.disabled = True
        self._index = 0

        target_y = (Window.height - self.height) / 2
        self.y = -self.height - 30
        Animation(
            y=target_y,
            opacity=1,
            duration=0.42,
            t="out_cubic",
        ).start(self)

        if self._printer_event:
            self._printer_event.cancel()
        self._printer_event = Clock.schedule_interval(self._print_line, 0.24)
        app.audio.play_sfx("receipt_printer.wav")

    def _quality_ru(self, quality):
        return {
            "perfect": "ИДЕАЛЬНО",
            "good": "ХОРОШО",
            "bad": "ОШИБКА",
        }.get(quality, "ХОРОШО")

    def _print_line(self, _dt):
        if self._index >= len(self._lines):
            if self._printer_event:
                self._printer_event.cancel()
                self._printer_event = None
            self.ids.save_btn.disabled = False
            return False

        self.ids.receipt_text.text += self._lines[self._index] + "\n"
        self._index += 1
        App.get_running_app().audio.play_printer()
        return True

    def save_receipt(self):
        if self._printer_event:
            self._printer_event.cancel()
            self._printer_event = None
        self.on_saved(self.note, self.result.quality)
        self.dismiss()


class DiaryScreen(AnimatedScreen):
    def on_enter(self, *_):
        super().on_enter()
        notes = App.get_running_app().save.data.get("diary", [])
        self.ids.diary_text.text = (
            "\n\n".join(
                f"#{index + 1}\n{note}"
                for index, note in enumerate(notes)
            )
            if notes
            else "Пока пусто.\nНекоторые мысли приходят только вместе с горячей чашкой."
        )

    def back(self):
        App.get_running_app().sm.current = "menu"


class SettingsPopup(Popup):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = "НАСТРОЙКИ"
        self.size_hint = (0.92, 0.90)
        self.background_color = (0, 0, 0, 0)

        app = App.get_running_app()
        settings = app.save.data["settings"]

        box = BoxLayout(
            orientation="vertical",
            padding=14,
            spacing=8,
        )

        for title, key in (
            ("Общая громкость", "master"),
            ("Музыка", "music"),
            ("Дождь / фон", "rain"),
            ("Звуки", "sfx"),
        ):
            box.add_widget(
                Label(
                    text=title,
                    font_name=FONT,
                    color=PALETTE["cream"],
                    size_hint_y=None,
                    height=24,
                )
            )
            slider = Slider(
                min=0,
                max=1,
                value=float(settings.get(key, 0.5)),
                size_hint_y=None,
                height=32,
            )
            box.add_widget(slider)
            slider.bind(
                value=lambda _w, value, setting_key=key: self._volume(
                    setting_key, value
                )
            )

        typewriter = ToggleButton(
            text="Печатная машинка: ВКЛ"
            if settings["typewriter"]
            else "Печатная машинка: ВЫКЛ",
            state="down" if settings["typewriter"] else "normal",
            font_name=FONT,
            size_hint_y=None,
            height=42,
        )
        animations = ToggleButton(
            text="Анимации: ВКЛ"
            if settings["animations"]
            else "Анимации: ВЫКЛ",
            state="down" if settings["animations"] else "normal",
            font_name=FONT,
            size_hint_y=None,
            height=42,
        )
        shake = ToggleButton(
            text="Тряска экрана: ВКЛ"
            if settings["screen_shake"]
            else "Тряска экрана: ВЫКЛ",
            state="down" if settings["screen_shake"] else "normal",
            font_name=FONT,
            size_hint_y=None,
            height=42,
        )

        box.add_widget(typewriter)
        box.add_widget(animations)
        box.add_widget(shake)

        save = PressButton(
            text="СОХРАНИТЬ",
            size_hint_y=None,
            height=46,
            background_color=PALETTE["sage"],
        )
        reset = PressButton(
            text="СБРОСИТЬ ПРОГРЕСС",
            background_color=PALETTE["rose"],
            size_hint_y=None,
            height=42,
        )
        box.add_widget(save)
        box.add_widget(reset)
        self.content = box

        typewriter.bind(
            state=lambda button, state: self._toggle(
                "typewriter", state, button, "Печатная машинка"
            )
        )
        animations.bind(
            state=lambda button, state: self._toggle(
                "animations", state, button, "Анимации"
            )
        )
        shake.bind(
            state=lambda button, state: self._toggle(
                "screen_shake", state, button, "Тряска экрана"
            )
        )
        save.bind(on_release=lambda *_: self._save_and_close())
        reset.bind(on_release=lambda *_: self._reset(app))

    def _volume(self, key, value):
        app = App.get_running_app()
        app.save.data["settings"][key] = float(value)
        app.audio.configure(app.save.data["settings"])

    def _toggle(self, key, state, button, title):
        enabled = state == "down"
        button.text = f"{title}: " + ("ВКЛ" if enabled else "ВЫКЛ")
        App.get_running_app().save.data["settings"][key] = enabled

    def _save_and_close(self):
        app = App.get_running_app()
        app.save.save()
        self.dismiss()

    def _reset(self, app):
        app.save.reset()
        self.dismiss()
        app.sm.current = "menu"


class TeaGameApp(App):
    title = "Сейко — Пузатый"

    def build(self):
        self.PALETTE = PALETTE
        self.FONT = FONT
        self.asset = asset

        self.save = SaveManager(SAVE_PATH)
        self.audio = AudioManager(asset)
        self.audio.configure(self.save.data["settings"])
        self.audio.set_playlist(PLAYLIST)
        self.audio.set_rain(RAIN_SOUND)
        self.ui = UIManager(self)

        kv_path = os.path.join(BASE_DIR, "ui.kv")
        try:
            Builder.load_file(kv_path)
        except Exception:
            log_path = os.path.join(
                os.environ.get("TEMP", BASE_DIR),
                "Seiko_Puzaty_startup_error.txt",
            )
            try:
                with open(log_path, "w", encoding="utf-8") as log:
                    traceback.print_exc(file=log)
            except OSError:
                pass
            raise

        Window.size = (360, 640)
        self.sm = ScreenManager(transition=FadeTransition(duration=0.22))

        self.sm.add_widget(MainMenu(name="menu"))
        self.coffee_screen = CoffeeShop(name="coffee")
        self.sm.add_widget(self.coffee_screen)

        self.minigame_screens = {
            "timing": TimingMiniGame(name="minigame_timing"),
            "stirring": StirringMiniGame(name="minigame_stirring"),
            "ingredients": IngredientMiniGame(name="minigame_ingredients"),
            "pouring": PouringMiniGame(name="minigame_pouring"),
        }
        for screen in self.minigame_screens.values():
            self.sm.add_widget(screen)

        self.sm.add_widget(DiaryScreen(name="diary"))

        Clock.schedule_once(
            lambda _dt: self.audio.start_background_audio(),
            1.0,
        )
        return self.sm

    def on_stop(self):
        try:
            if self.coffee_screen.character:
                self.coffee_screen.character.stop()
        except Exception:
            pass
        try:
            self.save.save()
        except Exception:
            pass
        try:
            self.audio.stop_all()
        except Exception:
            pass


if __name__ == "__main__":
    TeaGameApp().run()
