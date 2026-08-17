# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass
from typing import Dict, List, Tuple

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.audio import SoundLoader


@dataclass(frozen=True)
class Recipe:
    name: str
    base: str
    addon: str
    target_temp: Tuple[int, int]
    description: str


@dataclass(frozen=True)
class BrewResult:
    quality: str
    score: float
    recipe_match: float
    skill_score: float
    recipe: Recipe


@dataclass(frozen=True)
class StoryDay:
    weather: str
    intro: str
    endings: Dict[str, str]
    choices: Tuple[Tuple[str, int, str], ...]


class SaveManager:
    DEFAULT = {
        "version": 4,
        "day": 1,
        "relationship": 0,
        "history": [],
        "diary": [],
        "flags": {
            "choice_count": 0,
            "npc_clicks": 0,
            "perfect_streak": 0,
        },
        "settings": {
            "master": 0.9,
            "music": 0.38,
            "rain": 0.18,
            "sfx": 0.55,
            "typewriter": True,
            "animations": True,
            "screen_shake": True,
        },
    }

    def __init__(self, path: str):
        self.path = path
        self.data = json.loads(json.dumps(self.DEFAULT))
        self.load()

    def load(self) -> None:
        try:
            if not os.path.exists(self.path):
                return
            with open(self.path, "r", encoding="utf-8") as fh:
                incoming = json.load(fh)
            if not isinstance(incoming, dict):
                return

            for key, value in incoming.items():
                if key == "settings" and isinstance(value, dict):
                    self.data["settings"].update(value)
                elif key == "flags" and isinstance(value, dict):
                    self.data["flags"].update(value)
                elif key in self.data:
                    self.data[key] = value

            self._sanitize()
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            # Corrupt save must never prevent a new game from launching.
            self.data = json.loads(json.dumps(self.DEFAULT))

    def _sanitize(self) -> None:
        try:
            self.data["day"] = max(1, min(14, int(self.data.get("day", 1))))
        except (TypeError, ValueError):
            self.data["day"] = 1
        try:
            self.data["relationship"] = max(-8, min(25, int(self.data.get("relationship", 0))))
        except (TypeError, ValueError):
            self.data["relationship"] = 0
        if not isinstance(self.data.get("history"), list):
            self.data["history"] = []
        if not isinstance(self.data.get("diary"), list):
            self.data["diary"] = []
        if not isinstance(self.data.get("flags"), dict):
            self.data["flags"] = {}
        for key, default in self.DEFAULT["flags"].items():
            self.data["flags"].setdefault(key, default)
        if not isinstance(self.data.get("settings"), dict):
            self.data["settings"] = {}
        for key, default in self.DEFAULT["settings"].items():
            self.data["settings"].setdefault(key, default)

    def save(self) -> None:
        try:
            folder = os.path.dirname(self.path)
            if folder:
                os.makedirs(folder, exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except OSError:
            # A read-only directory should not crash the game.
            pass

    def reset(self) -> None:
        self.data = json.loads(json.dumps(self.DEFAULT))
        self.save()

    def add_diary(self, text: str) -> None:
        if text and text not in self.data["diary"]:
            self.data["diary"].append(text)
        self.save()

    # Backward compatible alias.
    add_receipt = add_diary

    def add_relationship(self, delta: int, reason: str = "") -> int:
        old = int(self.data.get("relationship", 0))
        new = max(-8, min(25, old + int(delta)))
        self.data["relationship"] = new
        self.data["flags"]["choice_count"] = int(self.data["flags"].get("choice_count", 0)) + 1
        if reason:
            self.add_diary(f"Маленькая заметка: {reason}")
        else:
            self.save()
        return new

    def record_brew(self, day: int, base: str, addon: str, quality: str, score: float) -> None:
        self.data["history"].append({
            "day": int(day),
            "base": base,
            "addon": addon,
            "quality": quality,
            "score": round(float(score), 3),
        })
        delta = {"perfect": 3, "good": 1, "bad": -1}.get(quality, 0)
        self.data["relationship"] = max(
            -8, min(25, int(self.data.get("relationship", 0)) + delta)
        )
        if quality == "perfect":
            self.data["flags"]["perfect_streak"] = int(self.data["flags"].get("perfect_streak", 0)) + 1
        else:
            self.data["flags"]["perfect_streak"] = 0
        self.save()


class AudioManager:
    """Fail-safe audio. Missing/unsupported codecs never block gameplay."""

    def __init__(self, asset):
        self.asset = asset
        self.settings = {}
        self.music = None
        self.rain = None
        self.sfx_cache = {}
        self.playlist = []
        self.rain_path = None
        self.index = 0
        self.started = False

    def _vol(self, key: str, default: float) -> float:
        try:
            master = max(0.0, min(1.0, float(self.settings.get("master", 0.9))))
            value = max(0.0, min(1.0, float(self.settings.get(key, default))))
            return master * value
        except (TypeError, ValueError):
            return 0.0

    def configure(self, settings):
        self.settings = settings if isinstance(settings, dict) else {}
        self._apply_volumes()

    def _load(self, path):
        if not path or not os.path.isfile(path):
            return None
        try:
            return SoundLoader.load(path)
        except Exception:
            return None

    def set_playlist(self, playlist):
        self.playlist = [p for p in (playlist or []) if os.path.isfile(p)]
        self.index = 0

    def set_rain(self, path):
        self.rain_path = path if path and os.path.isfile(path) else None

    load_music = set_playlist
    load_rain = set_rain

    def start_background_audio(self):
        if self.started:
            return
        self.started = True
        try:
            if self.playlist and self._vol("music", 0.38) > 0:
                self.play_music()
            if self.rain_path and self._vol("rain", 0.18) > 0:
                self._start_rain()
        except Exception:
            self.music = None
            self.rain = None

    def _start_rain(self):
        rain = self._load(self.rain_path)
        if rain is None:
            return
        try:
            rain.loop = True
            rain.volume = self._vol("rain", 0.18)
            rain.play()
            self.rain = rain
        except Exception:
            try:
                rain.stop()
            except Exception:
                pass

    def play_music(self):
        if not self.playlist or self._vol("music", 0.38) <= 0:
            return
        try:
            if self.music:
                try:
                    self.music.unbind(on_stop=self._music_finished)
                except Exception:
                    pass
                try:
                    self.music.stop()
                except Exception:
                    pass

            sound = self._load(self.playlist[self.index])
            if sound is None:
                self._advance_music()
                return

            sound.loop = False
            sound.volume = self._vol("music", 0.38)
            sound.bind(on_stop=self._music_finished)
            sound.play()
            self.music = sound
        except Exception:
            self.music = None

    def _advance_music(self, *args):
        if not self.playlist:
            return
        self.index = (self.index + 1) % len(self.playlist)
        if self.started:
            Clock.schedule_once(lambda _dt: self.play_music(), 0.15)

    def _music_finished(self, sound):
        try:
            sound.unbind(on_stop=self._music_finished)
        except Exception:
            pass
        self._advance_music()

    def play_sfx(self, name: str, restart: bool = True) -> bool:
        if self._vol("sfx", 0.55) <= 0:
            return False
        path = self.asset(name)
        if not os.path.isfile(path):
            return False
        try:
            sound = self.sfx_cache.get(name)
            if sound is None:
                sound = self._load(path)
                if sound is None:
                    return False
                self.sfx_cache[name] = sound
            if restart:
                try:
                    sound.stop()
                except Exception:
                    pass
            sound.volume = self._vol("sfx", 0.55)
            sound.play()
            return True
        except Exception:
            return False

    def play_purr(self):
        return self.play_sfx("purr.wav")

    def play_printer(self):
        return self.play_sfx("receipt_printer.wav")

    def _apply_volumes(self):
        if self.music:
            try:
                self.music.volume = self._vol("music", 0.38)
            except Exception:
                pass
        if self.rain:
            try:
                self.rain.volume = self._vol("rain", 0.18)
            except Exception:
                pass
        for sound in list(self.sfx_cache.values()):
            try:
                sound.volume = self._vol("sfx", 0.55)
            except Exception:
                pass

    def stop_all(self):
        for sound in (self.music, self.rain):
            if sound:
                try:
                    sound.stop()
                except Exception:
                    pass
        self.music = None
        self.rain = None
        self.started = False


class UIManager:
    def __init__(self, app):
        self.app = app

    @property
    def enabled(self):
        return bool(self.app.save.data["settings"].get("animations", True))

    @property
    def shake_enabled(self):
        return bool(self.app.save.data["settings"].get("screen_shake", True)) and self.enabled

    def fade_in(self, widget, duration=0.25, delay=0):
        if not self.enabled:
            widget.opacity = 1
            return
        widget.opacity = 0

        def start(_dt):
            Animation(opacity=1, duration=duration, t="out_quad").start(widget)

        Clock.schedule_once(start, delay)

    def pulse(self, widget):
        if not self.enabled:
            return
        (Animation(opacity=0.68, duration=0.06) +
         Animation(opacity=1, duration=0.12)).start(widget)

    def shake(self, widget, amount=5):
        if not self.shake_enabled:
            return
        x = widget.x
        (Animation(x=x + amount, duration=0.05) +
         Animation(x=x - amount, duration=0.07) +
         Animation(x=x + amount / 2, duration=0.05) +
         Animation(x=x, duration=0.06)).start(widget)


class StoryManager:
    NPCS = {
        "lena": (
            "Аой",
            "«Я учусь говорить о том, что мне нужно, до того, как это превратится в молчание».",
        ),
        "max": (
            "Рэн",
            "«Иногда забота — это не решение проблемы. Это вопрос: тебе сейчас нужна помощь или просто компания?»",
        ),
        "ira": (
            "Хина",
            "«Пауза — не отказ. Иногда пауза помогает ответить не из усталости».",
        ),
        "noah": (
            "Сора",
            "«Хороший разговор не обязан закончиться победителем».",
        ),
        "mira": (
            "Нао",
            "«Если человек замолчал, можно спросить мягко. Не обязательно угадывать».",
        ),
        "dan": (
            "Акира",
            "«Доверие складывается из маленьких предсказуемых вещей».",
        ),
    }

    DAYS: Dict[int, StoryDay] = {
        1: StoryDay(
            "Дождь стучит по стеклу, город пахнет мокрым асфальтом.",
            "Пузатый приходит мокрый. «Я просто пережидаю дождь».",
            {
                "perfect": "«Иногда дом — это место, где никто не спрашивает, почему ты промок».",
                "good": "«Сегодня достаточно просто не спешить».",
                "bad": "«Даже чай сегодня решил спорить со мной».",
            },
            (
                ("«Можешь просто посидеть рядом».", 2, "Сегодня важнее было присутствие, а не решение."),
                ("«Давай сразу разберём всё».", 0, "Ты выбрал прямоту."),
                ("«Наверное, это само пройдёт».", -1, "Ты заметил, как легко обесценить чувство поспешным ответом."),
            ),
        ),
        2: StoryDay(
            "Серое утро. Люди бегут, будто опаздывают в собственную жизнь.",
            "«Сегодня без спешки. Хочу вспомнить вкус настоящего утра».",
            {
                "perfect": "«Странно. Вроде просто кофе, а внутри стало тише».",
                "good": "«Пойдёт. Иногда этого достаточно».",
                "bad": "«Ох... это бодрит слишком честно».",
            },
            (
                ("«Что для тебя сделало бы это утро легче?»", 2, "Ты спросил не угадывая."),
                ("«Я знаю, что тебе нужно».", -1, "Уверенность без вопроса оказалась не очень точной."),
                ("«Расскажи, когда будешь готов».", 1, "Ты оставил пространство без давления."),
            ),
        ),
        3: StoryDay(
            "Ветер гоняет листья по мокрому тротуару.",
            "«Я кое-что понял вчера. Но пока не знаю, как это сказать».",
            {
                "perfect": "«Спасибо. Некоторые вещи лучше просто почувствовать».",
                "good": "«Почти попал. Может, и я когда-нибудь научусь».",
                "bad": "«Зато разговор получился интересным».",
            },
            (
                ("«Можешь попробовать с любого места».", 2, "Начинать разговор оказалось важнее идеальной формулировки."),
                ("«Скажи нормально».", -2, "Торопливость сделала слова тяжелее."),
                ("«Я послушаю, даже если получится сумбурно».", 2, "Безопасность иногда начинается с разрешения быть несовершенным."),
            ),
        ),
        4: StoryDay(
            "Ночь. Неон дрожит в лужах.",
            "«У тебя бывало место, где тебя ждут, даже если ты ничего не обещал?»",
            {
                "perfect": "«Наверное, я поэтому сюда возвращаюсь».",
                "good": "«Знаешь, здесь всё равно хорошо».",
                "bad": "«Спасибо, что оставил свет включённым».",
            },
            (
                ("«Да. И я хочу, чтобы ты мог приходить без объяснений».", 2, "Ты выбрал принятие без требований."),
                ("«Тогда обещай приходить».", -1, "Близость не всегда должна превращаться в обязательство."),
                ("«Мне приятно это слышать».", 1, "Ты принял признание без давления."),
            ),
        ),
        5: StoryDay(
            "Утро после дождя. Город стал немного светлее.",
            "«Кажется, я кое-что решил».",
            {
                "perfect": "«Я больше не буду считать это место случайностью».",
                "good": "«Я вернусь завтра. Наверное, это уже ответ».",
                "bad": "«Неидеально. Зато по-настоящему».",
            },
            (
                ("«Не торопись. Решение можно обсудить».", 2, "Вы оставили место для изменения решения."),
                ("«Наконец-то».", -1, "Ожидание оказалось заметнее, чем хотелось."),
                ("«Я рад, что ты поделился».", 1, "Ты сначала принял доверие, а уже потом думал о выводах."),
            ),
        ),
        6: StoryDay(
            "Холодный вечер. В окне напротив горит одно-единственное окно.",
            "«Я раньше думал, что возвращаться — значит проигрывать».",
            {
                "perfect": "«Оказывается, можно возвращаться не назад, а к себе».",
                "good": "«Мне спокойнее, когда я знаю, где свет».",
                "bad": "«Сегодня я опять убежал от себя. Ничего, завтра попробую не убегать».",
            },
            (
                ("«Спасибо, что вернулся и рассказал».", 2, "Возвращение стало не поражением, а продолжением разговора."),
                ("«Ты опять всё усложняешь».", -2, "Сложное чувство не стало проще от ярлыка."),
                ("«Хочешь чай или просто тишину?»", 2, "Ты предложил выбор вместо предположения."),
            ),
        ),
        7: StoryDay(
            "После дождя пахнет асфальтом и мокрой землёй.",
            "«Сегодня я пришёл не переждать погоду».",
            {
                "perfect": "«Я пришёл, потому что здесь меня знают. И, кажется, я тоже начал тебя знать».",
                "good": "«Спасибо за место. Я ещё не умею прощаться».",
                "bad": "«Даже если всё не получилось, я всё равно рад, что пришёл».",
            },
            (
                ("«Тогда давай не будем торопить финал».", 2, "Вы решили продолжить историю без давления."),
                ("«Значит, теперь всё хорошо?»", 0, "Один хороший вечер не обязан решать всё."),
                ("«Я рядом, даже если завтра будет сложнее».", 2, "Поддержка оказалась важнее обещания идеального завтра."),
            ),
        ),
        8: StoryDay(
            "Город просыпается раньше кофейни. На улице пахнет корицей.",
            "Пузатый впервые приходит не за напитком. «Можно я просто посижу?»",
            {
                "perfect": "«Иногда лучший разговор начинается с разрешения ничего не объяснять».",
                "good": "«Спасибо, что не стал чинить меня».",
                "bad": "«Сегодня слов мало. Но я всё равно остался».",
            },
            (
                ("«Конечно. Выбирай место».", 2, "Ты дал контроль там, где он был нужен."),
                ("«Но ты должен рассказать, что случилось».", -1, "Любопытство оказалось сильнее бережности."),
                ("«Можем просто посидеть».", 2, "Тишина стала общей, а не неловкой."),
            ),
        ),
        9: StoryDay(
            "Ветер стих. На окнах остаются маленькие капли.",
            "«Я заметил, что когда мне страшно, я начинаю говорить слишком резко».",
            {
                "perfect": "«Теперь я хотя бы замечаю это раньше».",
                "good": "«Наверное, мне ещё нужно потренироваться».",
                "bad": "«Я опять сказал лишнее. Извини».",
            },
            (
                ("«Спасибо, что заметил. Что поможет в следующий раз?»", 3, "Вы превратили конфликт в совместную задачу."),
                ("«Просто не говори резко».", -1, "Правило без поддержки редко помогает его выполнить."),
                ("«Если хочешь, можем сделать паузу».", 2, "Пауза стала инструментом, а не наказанием."),
            ),
        ),
        10: StoryDay(
            "Вечером вывеска кофейни отражается в каждой луже.",
            "«А что ты делаешь, когда сам устаёшь?»",
            {
                "perfect": "«Забавно. Я всё время учился просить помощь, а теперь учусь принимать её».",
                "good": "«Я не привык, что обо мне тоже спрашивают».",
                "bad": "«Наверное, я слишком долго делал вид, что справляюсь».",
            },
            (
                ("«Я тоже иногда не справляюсь. Можно быть двумя уставшими людьми».", 3, "Взаимность сделала разговор честнее."),
                ("«Я-то всегда справляюсь».", -1, "Сила без уязвимости создала дистанцию."),
                ("«Давай сегодня оба выберем что-то простое».", 2, "Вы уменьшили нагрузку вместо требований."),
            ),
        ),
        11: StoryDay(
            "Первый холод. Стекло запотевает от тепла внутри.",
            "«Мне страшно, что однажды ты устанешь от моих сложных дней».",
            {
                "perfect": "«Наверное, любовь — не обещание никогда не уставать. Это честность о том, когда сил мало».",
                "good": "«Спасибо, что не дал красивого, но невозможного обещания».",
                "bad": "«Я всё равно боюсь. Но теперь хотя бы могу сказать это».",
            },
            (
                ("«Я могу быть рядом и одновременно говорить, когда мне тяжело».", 3, "Границы и близость оказались совместимыми."),
                ("«Никогда не устану, обещаю».", 0, "Красивое обещание не решило страх."),
                ("«Давай не будем решать всю жизнь сегодня».", 2, "Будущее перестало давить."),
            ),
        ),
        12: StoryDay(
            "Ночь становится длиннее, но в кофейне теплее.",
            "«Сегодня я хочу научиться не проверять, всё ли между нами хорошо, каждые пять минут».",
            {
                "perfect": "«Оказывается, доверие иногда выглядит как тишина между сообщениями».",
                "good": "«Я попробую выдерживать паузу».",
                "bad": "«Мне всё ещё трудно. Но я тренируюсь».",
            },
            (
                ("«Если тревожно — можно спросить прямо, без проверки».", 3, "Прямой вопрос оказался мягче догадки."),
                ("«Просто перестань думать об этом».", -2, "Тревога не исчезла от приказа."),
                ("«Давай придумаем нашу маленькую фразу-проверку».", 2, "Вы создали общий, понятный сигнал."),
            ),
        ),
        13: StoryDay(
            "Перед закрытием город почти стих.",
            "«Мне кажется, я стал лучше понимать разницу между “мне страшно” и “ты сделал что-то не так”».",
            {
                "perfect": "«Это маленькая разница, но она меняет почти весь разговор».",
                "good": "«Я ещё путаюсь. Зато теперь замечаю».",
                "bad": "«Сегодня я снова перепутал страх с обвинением».",
            },
            (
                ("«Давай проверим факты вместе».", 3, "Вы отделили чувство от предположения."),
                ("«Вот видишь, ты опять».", -2, "Ошибка стала поводом для стыда вместо обучения."),
                ("«Можем вернуться к этому позже».", 2, "Отложить разговор иногда значит сохранить его."),
            ),
        ),
        14: StoryDay(
            "Последний вечер этой маленькой недели. За окном снова начинается дождь.",
            "Пузатый смотрит на пустую чашку. «Я думал, история закончится, когда закончится семь дней. А она почему-то продолжилась».",
            {
                "perfect": "«Я не хочу идеальную историю. Я хочу настоящую — с паузами, разговорами, ошибками и возвращениями».",
                "good": "«Спасибо за эти вечера. Думаю, завтра я всё равно загляну».",
                "bad": "«Даже плохие дни не отменяют хорошие. Наверное, это я запомню».",
            },
            (
                ("«Тогда давай оставим дверь открытой — без обещаний и без давления».", 3, "Финал стал началом без обязательства."),
                ("«Значит, мы всё решили».", 0, "История не обязана быть окончательно определена."),
                ("«Спасибо, что был здесь».", 2, "Благодарность стала последней репликой вечера."),
            ),
        ),
    }

    def day(self, day: int) -> StoryDay:
        return self.DAYS.get(day, self.DAYS[14])

    def weather(self, day: int) -> str:
        return self.day(day).weather

    def intro(self, day: int) -> str:
        return self.day(day).intro

    def choices(self, day: int):
        return self.day(day).choices

    def ending(self, day: int, quality: str, relationship: int) -> str:
        text = self.day(day).endings.get(quality, self.day(day).endings["good"])
        if day >= 12 and relationship >= 12 and quality == "perfect":
            text += " Пузатый улыбается: «Кажется, мы научились возвращаться к разговору, а не к старым ссорам»."
        if day == 14:
            if relationship >= 16:
                text += " В окне напротив загорается ещё один свет."
            elif relationship < 0:
                text += " На стойке остаётся записка: «Иногда забота начинается с честного “мне нужна пауза”»."
        return text

    NPC_VARIANTS = {
        "lena": [
            "«Иногда забота — это спросить, а не догадаться».",
            "«Мне легче говорить, когда меня не торопят».",
            "«Тишина рядом с правильным человеком не кажется пустой»."
        ],
        "max": [
            "«Если хочешь помочь, сначала узнай, что именно сейчас нужно».",
            "«Можно быть рядом и не чинить человека».",
            "«Хорошая поддержка оставляет человеку право выбрать»."
        ],
        "ira": [
            "«Пауза иногда спасает разговор от слов, о которых потом жалеешь».",
            "«Не каждый сложный вечер требует решения сегодня».",
            "«Я учусь говорить: мне нужно немного пространства»."
        ],
        "noah": [
            "«В споре можно выиграть фразу и проиграть близость».",
            "«Мне нравится, когда меня слышат до конца».",
            "«Извинение работает лучше, когда за ним что-то меняется»."
        ],
        "mira": [
            "«Если не знаешь, что сказать, можно честно сказать именно это».",
            "«Вопрос иногда теплее совета».",
            "«Не нужно читать мысли, если можно спросить»."
        ],
        "dan": [
            "«Доверие растёт из маленьких вещей, которые повторяются».",
            "«Предсказуемость — тоже форма заботы».",
            "«Когда обещаешь меньше, легче выполнить больше»."
        ],
    }

    def npc_quote(self, npc: str, day: int = 1, relationship: int = 0):
        label, fallback = self.NPCS.get(
            npc, ("Пузатый", "«Иногда достаточно просто остаться рядом»."),
        )
        variants = self.NPC_VARIANTS.get(npc, [fallback])
        index = (max(1, int(day)) + int(relationship) + len(npc)) % len(variants)
        return label, variants[index]


class RecipeManager:
    RECIPES = [
        Recipe("Дождливый сад", "Травяной чай", "Ягоды", (78, 84), "Травы, ягоды и немного тишины."),
        Recipe("Первый свет", "Кофе", "Корица", (88, 96), "Кофе с сухим пряным послевкусием."),
        Recipe("Зелёный ветер", "Зелёный чай", "Мята", (72, 80), "Свежий, но не кипящий."),
        Recipe("Ночная кружка", "Какао", "Ванильный сироп", (68, 76), "Мягкий сладкий свет после закрытия."),
        Recipe("Чёрное утро", "Чёрный чай", "Мёд", (88, 94), "Плотный чай для тяжёлого утра."),
        Recipe("Тихий мёд", "Кофе", "Мёд", (82, 90), "Мягкая горечь и тёплая сладость."),
        Recipe("Зелёный сад", "Зелёный чай", "Ягоды", (74, 82), "Холодная свежесть и лёгкая кислинка."),
        Recipe("Ванильный дождь", "Какао", "Мёд", (70, 78), "Сладкий, но спокойный вкус."),
        Recipe("Тихая ночь", "Травяной чай", "Мята", (74, 80), "Мятный аромат для длинного разговора."),
        Recipe("Тёплый город", "Кофе", "Ягоды", (84, 91), "Горький кофе с короткой ягодной нотой."),
        Recipe("Медовый вечер", "Чёрный чай", "Ванильный сироп", (86, 92), "Сухое тепло и мягкий финал."),
        Recipe("Зелёное окно", "Зелёный чай", "Мёд", (76, 82), "Лёгкая сладость без лишнего шума."),
        Recipe("Последний свет", "Какао", "Корица", (72, 80), "Тёплый напиток перед закрытием."),
        Recipe("Домой", "Кофе", "Ванильный сироп", (80, 88), "Финальная чашка: мягкая и знакомая."),
    ]
    DAY_RECIPE = {day: day - 1 for day in range(1, 15)}
    BASES = ["Чёрный чай", "Зелёный чай", "Травяной чай", "Какао", "Кофе"]
    ADDONS = ["Мята", "Корица", "Ягоды", "Мёд", "Ванильный сироп"]

    def recipe_for_day(self, day: int) -> Recipe:
        return self.RECIPES[self.DAY_RECIPE.get(day, 0)]

    def evaluate(self, day, base, addon, temp, skill_score):
        recipe = self.recipe_for_day(day)
        match = (0.55 if base == recipe.base else 0.0) + (0.45 if addon == recipe.addon else 0.0)
        low, high = recipe.target_temp
        if low <= temp <= high:
            temp_score = 1.0
        else:
            distance = min(abs(temp - low), abs(temp - high))
            temp_score = max(0.0, 1.0 - distance / 30.0)

        score = match * 0.58 + temp_score * 0.18 + float(skill_score) * 0.24
        quality = "perfect" if match >= 0.99 and temp_score >= 0.9 and skill_score >= 0.82 else (
            "good" if score >= 0.62 else "bad"
        )
        return BrewResult(quality, score, match, float(skill_score), recipe)


class ReceiptNarrativeManager:
    POOLS = {
        "perfect": [
            "«Сегодня ты сделал не напиток. Ты сделал место, в котором можно задержаться».",
            "«Иногда привязанность начинается с того, что кто-то помнит, сколько тебе нужно тепла».",
            "«Я всё ещё ищу себя. Но здесь искать почему-то не страшно».",
        ],
        "good": [
            "«Можно не быть идеальным, чтобы тебя ждали завтра».",
            "«Я заберу этот вечер с собой. Остальное оставлю здесь».",
            "«Почти получилось. Наверное, это честнее идеала».",
        ],
        "bad": [
            "«Ошибки пахнут горько, но почему-то я всё равно вернусь».",
            "«Сегодня чашка не спасла вечер. Спасибо, что попробовал».",
            "«У одиночества странный вкус. Может, завтра будет слаще».",
        ],
    }

    def get(self, day, quality, history, relationship=0):
        text = random.choice(self.POOLS.get(quality, self.POOLS["good"]))
        if relationship >= 10 and day >= 10:
            text += "\n«P.S. Мы уже умеем возвращаться к разговору»."
        if history and history[-1].get("quality") == "bad" and quality == "perfect":
            text += "\n«Видишь? Вторые попытки иногда самые настоящие»."
        return text


class CharacterManager:
    STATES = ("idle", "happy", "sad", "purr")

    def __init__(self, image_widget, asset, ui, audio):
        self.image = image_widget
        self.asset = asset
        self.ui = ui
        self.audio = audio
        self.paths = {state: asset(f"puzaty_{state}.png") for state in self.STATES}
        self.state = "idle"
        self._breath = None
        self._hold_event = None
        self.base_size = tuple(self.image.size)

    def _restore_base_size(self):
        self.image.size = self.base_size

    def set_state(self, state, hold=1.5):
        state = state if state in self.STATES else "idle"
        self.state = state

        path = self.paths[state]
        if os.path.exists(path):
            self.image.source = path
            self.image.reload()

        Animation.cancel_all(self.image)
        self._restore_base_size()

        if state == "happy":
            target = (self.base_size[0] * 1.06, self.base_size[1] * 1.06)
            (Animation(size=target, duration=0.12, t="out_back") +
             Animation(size=self.base_size, duration=0.18, t="out_quad")).start(self.image)
            self.audio.play_sfx("success.wav")
        elif state == "sad":
            self.ui.shake(self.image, 5)
            self.audio.play_sfx("mistake.wav")
        elif state == "purr":
            y = self.image.y
            (Animation(y=y + 4, duration=0.10) +
             Animation(y=y - 2, duration=0.14) +
             Animation(y=y, duration=0.10)).start(self.image)
            self.audio.play_purr()

        if self._hold_event:
            self._hold_event.cancel()
        if state != "idle":
            self._hold_event = Clock.schedule_once(
                lambda _dt: self.set_state("idle"),
                max(0.9, float(hold)),
            )

    def surprise(self):
        Animation.cancel_all(self.image)
        self._restore_base_size()
        target = (self.base_size[0] * 1.07, self.base_size[1] * 1.07)
        (Animation(size=target, duration=0.10, t="out_back") +
         Animation(size=self.base_size, duration=0.16)).start(self.image)
        self.audio.play_sfx("ui_click.wav")

    def perfect(self):
        self.set_state("happy")

    def mistake(self):
        self.set_state("sad", 2.8)

    def purr(self):
        self.set_state("purr", 2.0)

    def start_idle_breath(self):
        self.stop()
        base = self.base_size
        phase = [0]

        def tick(_dt):
            if self.state != "idle":
                return
            phase[0] += 1
            factor = 1.0 + (0.004 if phase[0] % 2 == 0 else -0.004)
            Animation(
                size=(base[0] * factor, base[1] * factor),
                duration=0.55,
                t="in_out_sine",
            ).start(self.image)

        self._breath = Clock.schedule_interval(tick, 0.62)

    def stop(self):
        if self._breath:
            self._breath.cancel()
            self._breath = None
        if self._hold_event:
            self._hold_event.cancel()
            self._hold_event = None
        Animation.cancel_all(self.image)
        self._restore_base_size()


class MinigameEngine:
    MODES = ("timing", "stirring", "ingredients", "pouring")

    def __init__(self, screen, audio):
        self.screen = screen
        self.audio = audio
        self.mode = "timing"
        self.score = 0.0
        self.active = False

    def start(self, mode=None):
        self.mode = mode if mode in self.MODES else random.choice(self.MODES)
        self.score = 0.0
        self.active = True

    def finish(self, score):
        self.active = False
        self.score = max(0.0, min(1.0, float(score)))
        return self.score

    def timing_score(self, cursor, target_center, target_width):
        half = max(1.0, target_width / 2.0)
        distance = abs(float(cursor) - float(target_center))
        # Outside the target zone is a real miss: it can never score enough
        # to pass the minigame threshold in MiniGameBase.finish().
        if distance > half:
            outside = distance - half
            return max(0.0, 0.35 - outside / max(8.0, target_width * 1.4) * 0.35)
        # Inside the zone, the center is perfect and the edge is still good
        # enough to pass, but visibly worse than a centered hit.
        return max(0.75, min(1.0, 1.0 - (distance / half) * 0.25))

    def stirring_score(self, revolutions, avg_speed, target_speed):
        speed_part = max(0.0, 1.0 - abs(avg_speed - target_speed) / max(1.0, target_speed))
        rev_part = min(1.0, revolutions / 2.2)
        return max(0.0, min(1.0, speed_part * 0.65 + rev_part * 0.35))

    def ingredient_score(self, caught_good, missed_good, caught_bad):
        total_good = max(1, caught_good + missed_good)
        return max(0.0, min(1.0, caught_good / total_good - min(0.7, caught_bad * 0.18)))

    def pouring_score(self, value, target_start, target_end):
        center = (float(target_start) + float(target_end)) / 2.0
        half = max(1.0, (float(target_end) - float(target_start)) / 2.0)
        distance = abs(float(value) - center)
        if distance > half:
            return max(0.0, 0.32 - (distance - half) / 30.0)
        return max(0.0, min(1.0, 1.0 - (distance / half) * 0.35))
