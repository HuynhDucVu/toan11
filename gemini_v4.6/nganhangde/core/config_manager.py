from __future__ import annotations
import configparser
from pathlib import Path
from ..paths import bundle_root, is_frozen, user_data_dir


DEFAULT_CONFIG = {
    "API": {
        "gemini_api_key": "",
        "gemini_model": "gemini-2.5-flash",
        "claude_api_key": "",
        "claude_model": "claude-sonnet-4-20250514",
        "ai_provider": "gemini",
        "mathpix_app_id": "",
        "mathpix_app_key": "",
    },
    "Tikz2Pic": {
        "dpi": "150",
        "question_color": "#006666",
        "solution_color": "#80FF80",
        "compiler": "pdflatex",
    },
    "BloggerForm": {
        "form_action_url": "",
        "entry_exam_name": "",
        "entry_sbd": "",
        "entry_student_name": "",
        "entry_class": "",
        "entry_score": "",
        "entry_answers": "",
        "entry_duration": "",
    },
    "Word2TeX": {
        "mode": "toggle_tex",
        "show_word": "1",
        "convert_table": "1",
    },
    "Theme": {
        "bg_color": "#F7F9FC",
        "fg_color": "#1E293B",
        "accent_color": "#006666",
    },
}


class ConfigManager:
    def __init__(self, ini_path: Path | None = None):
        if ini_path is not None:
            self.ini_path = Path(ini_path)
        else:
            self.ini_path = user_data_dir() / "config.ini"
        self.parser = configparser.ConfigParser()
        self.load()

    def load(self) -> None:
        for section, kv in DEFAULT_CONFIG.items():
            if not self.parser.has_section(section):
                self.parser.add_section(section)
            for k, v in kv.items():
                self.parser.set(section, k, v)
        if self.ini_path.exists():
            self.parser.read(self.ini_path, encoding="utf-8")

    def save(self) -> None:
        self.ini_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.ini_path, "w", encoding="utf-8") as f:
            self.parser.write(f)

    def get(self, section: str, key: str, fallback: str = "") -> str:
        return self.parser.get(section, key, fallback=fallback)

    def set(self, section: str, key: str, value: str) -> None:
        if not self.parser.has_section(section):
            self.parser.add_section(section)
        self.parser.set(section, key, str(value))
