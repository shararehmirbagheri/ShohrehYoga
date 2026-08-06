from datetime import date, datetime

import jdatetime
import arabic_reshaper
from bidi.algorithm import get_display

from kivy.graphics import Color, RoundedRectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup


PERSIAN_MONTHS = (
    "",
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
)

# Saturday through Friday
PERSIAN_WEEKDAYS = ("ش", "ی", "د", "س", "چ", "پ", "ج")

PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
ENGLISH_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def shape_persian(value):
    """Shape Persian text once for Kivy widgets created in Python."""
    if not value:
        return ""
    return get_display(arabic_reshaper.reshape(str(value)))


def to_persian_digits(value):
    return str(value).translate(PERSIAN_DIGITS)


def to_english_digits(value):
    return str(value).translate(ENGLISH_DIGITS)


def gregorian_iso_to_jalali_display(iso_date):
    """
    Return a Jalali date using ASCII numerals.

    Kivy TextInput on Windows can display Persian digits as square boxes
    when the widget does not receive the custom font early enough.
    ASCII digits keep the Jalali date readable and reliable everywhere.
    Example: 1405/05/12
    """
    if not iso_date:
        return ""
    value = datetime.strptime(iso_date, "%Y-%m-%d").date()
    jalali = jdatetime.date.fromgregorian(date=value)
    return f"{jalali.year:04d}/{jalali.month:02d}/{jalali.day:02d}"


def jalali_display_to_gregorian_iso(display_date):
    cleaned = to_english_digits(display_date).replace("-", "/").strip()
    year_text, month_text, day_text = cleaned.split("/")
    jalali = jdatetime.date(
        int(year_text),
        int(month_text),
        int(day_text),
    )
    return jalali.togregorian().isoformat()


def _jalali_month_days(year, month):
    if month <= 6:
        return 31
    if month <= 11:
        return 30
    return 30 if jdatetime.date.isleap(year) else 29


def open_jalali_date_picker(
    current_gregorian_iso,
    on_select,
    title=shape_persian("انتخاب تاریخ"),
):
    """
    Open a Persian/Jalali calendar.

    current_gregorian_iso:
        ISO Gregorian date used internally by SQLite, for example 2026-08-02.

    on_select:
        Callback receiving:
            gregorian_iso, jalali_display
    """
    try:
        current_gregorian = datetime.strptime(
            current_gregorian_iso,
            "%Y-%m-%d",
        ).date()
    except (TypeError, ValueError):
        current_gregorian = date.today()

    selected_jalali = jdatetime.date.fromgregorian(date=current_gregorian)
    today_jalali = jdatetime.date.today()

    state = {
        "year": selected_jalali.year,
        "month": selected_jalali.month,
    }

    root = BoxLayout(
        orientation="vertical",
        padding=12,
        spacing=9,
    )

    # Violet calendar header.
    header = BoxLayout(
        size_hint_y=None,
        height=58,
        spacing=8,
        padding=[8, 6, 8, 6],
    )
    with header.canvas.before:
        Color(0.42, 0.16, 0.72, 1)
        header._background = RoundedRectangle(
            pos=header.pos,
            size=header.size,
            radius=[10],
        )
    header.bind(
        pos=lambda widget, value: setattr(widget._background, "pos", value),
        size=lambda widget, value: setattr(widget._background, "size", value),
    )

    previous_button = Button(
        text="<",
        font_name="Persian",
        font_size=20,
        size_hint_x=None,
        width=55,
        background_normal="",
        background_color=(0.62, 0.42, 0.78, 1),
        color=(1, 1, 1, 1),
    )

    month_label = Label(
        text="",
        font_name="Persian",
        font_size=22,
        bold=True,
        color=(1, 1, 1, 1),
        halign="center",
        valign="middle",
    )
    month_label.bind(
        size=lambda widget, size: setattr(widget, "text_size", size)
    )

    next_button = Button(
        text=">",
        font_name="Persian",
        font_size=20,
        size_hint_x=None,
        width=55,
        background_normal="",
        background_color=(0.62, 0.42, 0.78, 1),
        color=(1, 1, 1, 1),
    )

    header.add_widget(previous_button)
    header.add_widget(month_label)
    header.add_widget(next_button)

    weekday_grid = GridLayout(
        cols=7,
        size_hint_y=None,
        height=38,
        spacing=3,
    )
    for weekday in PERSIAN_WEEKDAYS:
        weekday_grid.add_widget(
            Label(
                text=shape_persian(weekday),
                font_name="Persian",
                font_size=16,
                bold=True,
                color=(0.42, 0.16, 0.72, 1),
            )
        )

    days_grid = GridLayout(cols=7, spacing=4)

    footer = BoxLayout(
        size_hint_y=None,
        height=46,
        spacing=8,
    )

    cancel_button = Button(
        text=shape_persian("انصراف"),
        font_name="Persian",
        background_normal="",
        background_color=(0.62, 0.42, 0.78, 1),
        color=(1, 1, 1, 1),
    )

    today_button = Button(
        text=shape_persian("امروز"),
        font_name="Persian",
        background_normal="",
        background_color=(0.50, 0.20, 0.82, 1),
        color=(1, 1, 1, 1),
    )

    footer.add_widget(cancel_button)
    footer.add_widget(today_button)

    root.add_widget(header)
    root.add_widget(weekday_grid)
    root.add_widget(days_grid)
    root.add_widget(footer)

    popup = Popup(
        title=shape_persian(title),
        title_font="Persian",
        title_size=18,
        separator_color=(0.50, 0.20, 0.82, 1),
        content=root,
        size_hint=(0.72, 0.80),
        auto_dismiss=False,
    )

    def choose_date(year, month, day):
        jalali = jdatetime.date(year, month, day)
        gregorian_iso = jalali.togregorian().isoformat()
        jalali_display = f"{year:04d}/{month:02d}/{day:02d}"
        popup.dismiss()
        on_select(gregorian_iso, jalali_display)

    def render_month():
        days_grid.clear_widgets()

        year = state["year"]
        month = state["month"]

        month_label.text = shape_persian(
            f"{PERSIAN_MONTHS[month]} {year}"
        )

        first_day = jdatetime.date(year, month, 1)

        # Python weekday: Monday=0 ... Sunday=6.
        # Convert to Persian week: Saturday=0 ... Friday=6.
        first_column = (first_day.togregorian().weekday() + 2) % 7

        for _ in range(first_column):
            days_grid.add_widget(Label(text=""))

        for day_number in range(1, _jalali_month_days(year, month) + 1):
            candidate = jdatetime.date(year, month, day_number)

            is_selected = candidate == selected_jalali
            is_today = candidate == today_jalali

            if is_selected:
                background = (0.50, 0.20, 0.82, 1)
                foreground = (1, 1, 1, 1)
            elif is_today:
                background = (0.84, 0.73, 0.96, 1)
                foreground = (0.20, 0.10, 0.28, 1)
            else:
                background = (0.96, 0.94, 0.99, 1)
                foreground = (0.20, 0.10, 0.28, 1)

            day_button = Button(
                text=str(day_number),
                font_name="Persian",
                font_size=16,
                background_normal="",
                background_down="",
                background_color=background,
                color=foreground,
            )
            day_button.bind(
                on_release=lambda _instance, d=day_number, y=year, m=month:
                choose_date(y, m, d)
            )
            days_grid.add_widget(day_button)

    def previous_month(*_):
        state["month"] -= 1
        if state["month"] == 0:
            state["month"] = 12
            state["year"] -= 1
        render_month()

    def next_month(*_):
        state["month"] += 1
        if state["month"] == 13:
            state["month"] = 1
            state["year"] += 1
        render_month()

    previous_button.bind(on_release=previous_month)
    next_button.bind(on_release=next_month)
    cancel_button.bind(on_release=lambda *_: popup.dismiss())

    def select_today(*_):
        today = jdatetime.date.today()
        choose_date(today.year, today.month, today.day)

    today_button.bind(on_release=select_today)

    render_month()
    popup.open()
