import configparser
import json
import os
import sys

_LANG_DIR = os.path.join(os.path.dirname(__file__), "..", "resources", "lang")

AVAILABLE_LANGS = {
    "es": "Español",
    "en": "English",
    "pt_br": "Português (BR)",
}

_strings: dict = {}
_fallback: dict = {}
_current_lang: str = "es"


def _get_config_path() -> str:
    # En exe compilado, sys.executable es el .exe; en script, usamos su directorio
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "config.ini")


def _load_config() -> str:
    cfg = configparser.ConfigParser()
    try:
        cfg.read(_get_config_path(), encoding="utf-8")
        return cfg.get("general", "lang", fallback="es")
    except Exception:
        return "es"


def save_lang(lang_code: str):
    path = _get_config_path()
    cfg = configparser.ConfigParser()
    try:
        cfg.read(path, encoding="utf-8")
        if not cfg.has_section("general"):
            cfg.add_section("general")
        cfg.set("general", "lang", lang_code)
        with open(path, "w", encoding="utf-8") as f:
            cfg.write(f)
    except Exception as e:
        print(f"[lang] Error guardando config: {e}")


def get_current_lang() -> str:
    return _current_lang


def _load_json(lang_code: str) -> dict:
    path = os.path.join(_LANG_DIR, f"{lang_code}.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[lang] Error cargando {lang_code}.json: {e}")
        return {}


def init():
    global _strings, _fallback, _current_lang
    _fallback = _load_json("es")
    _current_lang = _load_config()
    _strings = _load_json(_current_lang) if _current_lang != "es" else _fallback


def _resolve(data: dict, parts: list):
    val = data
    for p in parts:
        if isinstance(val, dict):
            val = val.get(p)
        else:
            return None
        if val is None:
            return None
    return val


def t(key: str, **kwargs) -> str:
    if not _fallback:
        init()
    parts = key.split(".")
    val = _resolve(_strings, parts)
    if val is None:
        val = _resolve(_fallback, parts)
    if val is None:
        return key
    if kwargs:
        try:
            return str(val).format(**kwargs)
        except Exception:
            return str(val)
    return str(val)