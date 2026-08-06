from pathlib import Path

from kivy.app import App
from kivy.core.text import LabelBase
from kivy.lang import Builder
from kivy.uix.screenmanager import Screen

from attendance import AttendanceScreen, AttendanceStudentRow
from student import (
    PersianTextInput,
    StudentListScreen,
    StudentRow,
)

BASE_DIR = Path(__file__).resolve().parent
FONT_FILE = BASE_DIR / "fonts" / "Vazirmatn-Regular.ttf"
KV_FILE = BASE_DIR / "kv" / "main.kv"

if not FONT_FILE.exists():
    raise FileNotFoundError(f"Font file not found: {FONT_FILE}")

if not KV_FILE.exists():
    raise FileNotFoundError(f"KV file not found: {KV_FILE}")

LabelBase.register(
    name="Persian",
    fn_regular=str(FONT_FILE),
)


class HomeScreen(Screen):
    pass


class ReportScreen(Screen):
    pass


class YogaApp(App):
    def build(self):
        return Builder.load_file(str(KV_FILE))


if __name__ == "__main__":
    YogaApp().run()
