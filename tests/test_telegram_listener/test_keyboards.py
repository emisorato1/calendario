"""Tests para agents/telegram_listener/keyboards.py — Teclados de Telegram."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

from agents.telegram_listener.keyboards import (
    ADMIN_MAIN_MENU,
    CONFIRM_KEYBOARD,
    EDITOR_MAIN_MENU,
    build_date_suggestion_keyboard,
    build_day_full_keyboard,
    build_event_selection_keyboard,
    build_list_submenu_keyboard,
    build_time_slot_keyboard,
    get_main_menu,
)


# ── Menús estáticos ──────────────────────────────────────────────────────────


class TestMainMenus:
    """Tests para menús principales fijos."""

    def test_admin_main_menu_es_reply_keyboard(self):
        """ADMIN_MAIN_MENU es un ReplyKeyboardMarkup."""
        assert isinstance(ADMIN_MAIN_MENU, ReplyKeyboardMarkup)

    def test_admin_main_menu_tiene_4_botones(self):
        """Admin → 4 botones en 2 filas × 2."""
        # keyboard es una tupla de tuplas
        all_buttons = [btn for row in ADMIN_MAIN_MENU.keyboard for btn in row]
        assert len(all_buttons) == 4

    def test_admin_main_menu_tiene_crear_turno(self):
        """Admin tiene botón 'Crear Turno'."""
        all_buttons = [btn for row in ADMIN_MAIN_MENU.keyboard for btn in row]
        textos = [str(b) for b in all_buttons]
        assert any("Crear Turno" in t for t in textos)

    def test_editor_main_menu_es_reply_keyboard(self):
        """EDITOR_MAIN_MENU es un ReplyKeyboardMarkup."""
        assert isinstance(EDITOR_MAIN_MENU, ReplyKeyboardMarkup)

    def test_editor_main_menu_tiene_2_botones(self):
        """Editor → 2 botones en 1 fila."""
        all_buttons = [btn for row in EDITOR_MAIN_MENU.keyboard for btn in row]
        assert len(all_buttons) == 2

    def test_editor_main_menu_no_tiene_crear_turno(self):
        """Editor NO tiene botón 'Crear Turno'."""
        all_buttons = [btn for row in EDITOR_MAIN_MENU.keyboard for btn in row]
        textos = [str(b) for b in all_buttons]
        assert not any("Crear Turno" in t for t in textos)

    def test_editor_main_menu_no_tiene_cancelar(self):
        """Editor NO tiene botón 'Cancelar Evento'."""
        all_buttons = [btn for row in EDITOR_MAIN_MENU.keyboard for btn in row]
        textos = [str(b) for b in all_buttons]
        assert not any("Cancelar Evento" in t for t in textos)


# ── get_main_menu ────────────────────────────────────────────────────────────


class TestGetMainMenu:
    """Tests para get_main_menu()."""

    def test_admin_retorna_admin_menu(self, mock_settings):
        """Admin → ADMIN_MAIN_MENU."""
        menu = get_main_menu(123456789, mock_settings)
        assert menu is ADMIN_MAIN_MENU

    def test_editor_retorna_editor_menu(self, mock_settings):
        """Editor → EDITOR_MAIN_MENU."""
        menu = get_main_menu(111222333, mock_settings)
        assert menu is EDITOR_MAIN_MENU

    def test_desconocido_retorna_editor_menu(self, mock_settings):
        """Desconocido (no admin) → EDITOR_MAIN_MENU."""
        menu = get_main_menu(999999999, mock_settings)
        assert menu is EDITOR_MAIN_MENU


# ── CONFIRM_KEYBOARD ─────────────────────────────────────────────────────────


class TestConfirmKeyboard:
    """Tests para el teclado de confirmación."""

    def test_es_inline_keyboard(self):
        """CONFIRM_KEYBOARD es un InlineKeyboardMarkup."""
        assert isinstance(CONFIRM_KEYBOARD, InlineKeyboardMarkup)

    def test_tiene_2_botones(self):
        """Tiene Confirmar y Cancelar."""
        all_buttons = [btn for row in CONFIRM_KEYBOARD.inline_keyboard for btn in row]
        assert len(all_buttons) == 2

    def test_callbacks_correctos(self):
        """Callbacks son 'confirm' y 'cancel'."""
        all_buttons = [btn for row in CONFIRM_KEYBOARD.inline_keyboard for btn in row]
        callbacks = {btn.callback_data for btn in all_buttons}
        assert callbacks == {"confirm", "cancel"}


# ── build_time_slot_keyboard ─────────────────────────────────────────────────


class TestBuildTimeSlotKeyboard:
    """Tests para build_time_slot_keyboard()."""

    def test_lunes_sin_eventos_genera_botones(self, mock_settings):
        """Lunes sin eventos → al menos un botón de rango horario."""
        fecha = date(2026, 3, 2)
        kb = build_time_slot_keyboard(fecha, 2.0, mock_settings, [])
        assert isinstance(kb, InlineKeyboardMarkup)
        # Mínimo hay botones de rango + "¿Otro horario?"
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert len(all_buttons) >= 2  # al menos 1 slot + otro_horario

    def test_tiene_boton_otro_horario(self, mock_settings):
        """Siempre tiene botón '¿Otro horario?' al final."""
        fecha = date(2026, 3, 2)
        kb = build_time_slot_keyboard(fecha, 1.0, mock_settings, [])
        last_row = kb.inline_keyboard[-1]
        assert any(btn.callback_data == "other_time" for btn in last_row)

    def test_formato_rango_horario(self, mock_settings):
        """Los botones tienen formato 'HH:MM - HH:MM'."""
        fecha = date(2026, 3, 2)
        kb = build_time_slot_keyboard(fecha, 1.0, mock_settings, [])
        # Primer botón de rango (no el "otro horario")
        first_button = kb.inline_keyboard[0][0]
        assert " - " in first_button.text
        assert first_button.callback_data.startswith("time_slot:")

    def test_excluye_rangos_solapados(self, mock_settings):
        """Evento 15:00-17:00 → rangos solapados no aparecen."""
        fecha = date(2026, 3, 2)
        eventos = [
            {
                "start": {"dateTime": "2026-03-02T15:00:00-03:00"},
                "end": {"dateTime": "2026-03-02T17:00:00-03:00"},
            }
        ]
        kb_con = build_time_slot_keyboard(fecha, 1.0, mock_settings, eventos)
        kb_sin = build_time_slot_keyboard(fecha, 1.0, mock_settings, [])

        # Con evento tiene menos botones
        btns_con = [
            b
            for row in kb_con.inline_keyboard
            for b in row
            if b.callback_data.startswith("time_slot:")
        ]
        btns_sin = [
            b
            for row in kb_sin.inline_keyboard
            for b in row
            if b.callback_data.startswith("time_slot:")
        ]
        assert len(btns_con) < len(btns_sin)

    def test_filas_de_2_botones(self, mock_settings):
        """Los botones de rango se agrupan en filas de 2."""
        fecha = date(2026, 3, 7)  # Sábado, más slots
        kb = build_time_slot_keyboard(fecha, 1.0, mock_settings, [])
        # Todas las filas excepto la última tienen max 2 botones
        for row in kb.inline_keyboard[:-1]:
            assert len(row) <= 2


# ── build_day_full_keyboard ──────────────────────────────────────────────────


class TestBuildDayFullKeyboard:
    """Tests para build_day_full_keyboard()."""

    def test_tiene_boton_elegir_otro_dia(self):
        """Tiene botón '📅 Elegir otro día'."""
        kb = build_day_full_keyboard(date(2026, 3, 2))
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert any("Elegir otro día" in btn.text for btn in all_buttons)

    def test_tiene_boton_urgente(self):
        """Tiene botón '🚨 Es urgente — agendar igual'."""
        kb = build_day_full_keyboard(date(2026, 3, 2))
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert any("urgente" in btn.text.lower() for btn in all_buttons)

    def test_callbacks_correctos(self):
        """Callbacks son 'choose_other_day' y 'urgent_override'."""
        kb = build_day_full_keyboard(date(2026, 3, 2))
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        callbacks = {btn.callback_data for btn in all_buttons}
        assert "choose_other_day" in callbacks
        assert "urgent_override" in callbacks


# ── build_date_suggestion_keyboard ───────────────────────────────────────────


class TestBuildDateSuggestionKeyboard:
    """Tests para build_date_suggestion_keyboard()."""

    def test_retorna_inline_keyboard(self):
        """Retorna InlineKeyboardMarkup."""
        kb = build_date_suggestion_keyboard()
        assert isinstance(kb, InlineKeyboardMarkup)

    def test_tiene_5_botones(self):
        """4 fechas rápidas + '¿Otra fecha?' = 5 botones."""
        kb = build_date_suggestion_keyboard()
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert len(all_buttons) == 5

    def test_tiene_boton_hoy(self):
        """Tiene botón 'Hoy'."""
        kb = build_date_suggestion_keyboard()
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert any(btn.text == "Hoy" for btn in all_buttons)

    def test_tiene_boton_manana(self):
        """Tiene botón 'Mañana'."""
        kb = build_date_suggestion_keyboard()
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert any(btn.text == "Mañana" for btn in all_buttons)

    def test_tiene_boton_otra_fecha(self):
        """Tiene botón '¿Otra fecha?'."""
        kb = build_date_suggestion_keyboard()
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert any(btn.callback_data == "other_date" for btn in all_buttons)

    def test_callbacks_tienen_formato_date(self):
        """Los 4 botones de fecha tienen callback 'date:YYYY-MM-DD'."""
        kb = build_date_suggestion_keyboard()
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        date_buttons = [btn for btn in all_buttons if btn.callback_data.startswith("date:")]
        assert len(date_buttons) == 4
        for btn in date_buttons:
            fecha_str = btn.callback_data.split(":", 1)[1]
            # Debe ser fecha ISO válida
            date.fromisoformat(fecha_str)


# ── build_event_selection_keyboard ───────────────────────────────────────────


class TestBuildEventSelectionKeyboard:
    """Tests para build_event_selection_keyboard()."""

    def test_numera_eventos(self, evento_proximo, evento_proximo_2):
        """Genera botones [1], [2] para 2 eventos."""
        kb = build_event_selection_keyboard([evento_proximo, evento_proximo_2])
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert len(all_buttons) == 2
        assert all_buttons[0].text == "[1]"
        assert all_buttons[1].text == "[2]"

    def test_callbacks_tienen_formato_select_event(self, evento_proximo):
        """Callbacks tienen formato 'select_event:N'."""
        kb = build_event_selection_keyboard([evento_proximo])
        btn = kb.inline_keyboard[0][0]
        assert btn.callback_data == "select_event:1"

    def test_lista_vacia_genera_keyboard_vacio(self):
        """Lista vacía → keyboard sin botones."""
        kb = build_event_selection_keyboard([])
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert len(all_buttons) == 0

    def test_filas_de_5_botones(self):
        """Agrupa hasta 5 botones por fila."""
        eventos = [{"id": f"evt_{i}"} for i in range(7)]
        kb = build_event_selection_keyboard(eventos)
        assert len(kb.inline_keyboard[0]) == 5
        assert len(kb.inline_keyboard[1]) == 2


# ── build_list_submenu_keyboard ──────────────────────────────────────────────


class TestBuildListSubmenuKeyboard:
    """Tests para build_list_submenu_keyboard()."""

    def test_tiene_4_opciones(self):
        """Submenú tiene 4 botones de filtro."""
        kb = build_list_submenu_keyboard()
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert len(all_buttons) == 4

    def test_callbacks_tienen_prefijo_list(self):
        """Todos los callbacks empiezan con 'list:'."""
        kb = build_list_submenu_keyboard()
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        for btn in all_buttons:
            assert btn.callback_data.startswith("list:")

    def test_tiene_todas_las_opciones(self):
        """Tiene pendientes, dia, cliente, historial."""
        kb = build_list_submenu_keyboard()
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        callbacks = {btn.callback_data for btn in all_buttons}
        assert callbacks == {
            "list:pendientes",
            "list:dia",
            "list:cliente",
            "list:historial",
        }
