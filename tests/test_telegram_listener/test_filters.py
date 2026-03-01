"""Tests para agents/telegram_listener/filters.py — Filtros de autorización."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agents.telegram_listener.filters import (
    AdminOnlyFilter,
    AuthorizedUserFilter,
    EditorOrAdminFilter,
)


# ── AuthorizedUserFilter ─────────────────────────────────────────────────────


class TestAuthorizedUserFilter:
    """Tests para AuthorizedUserFilter."""

    def test_deja_pasar_admin(self, mock_settings):
        """Admin ID → filtro pasa."""
        f = AuthorizedUserFilter(mock_settings)
        msg = MagicMock()
        msg.from_user.id = 123456789  # admin
        assert f.filter(msg) is True

    def test_deja_pasar_editor(self, mock_settings):
        """Editor ID → filtro pasa."""
        f = AuthorizedUserFilter(mock_settings)
        msg = MagicMock()
        msg.from_user.id = 111222333  # editor
        assert f.filter(msg) is True

    def test_bloquea_desconocido(self, mock_settings):
        """Usuario fuera de ambas listas → filtro no pasa."""
        f = AuthorizedUserFilter(mock_settings)
        msg = MagicMock()
        msg.from_user.id = 999999999  # desconocido
        msg.from_user.username = "hacker"
        assert f.filter(msg) is False

    def test_bloquea_desconocido_con_log_warning(self, mock_settings):
        """Usuario no autorizado genera log WARNING."""
        f = AuthorizedUserFilter(mock_settings)
        msg = MagicMock()
        msg.from_user.id = 999999999
        msg.from_user.username = "hacker"
        with patch("agents.telegram_listener.filters.log") as mock_log:
            f.filter(msg)
            mock_log.warning.assert_called_once()

    def test_bloquea_mensaje_sin_usuario(self, mock_settings):
        """Mensaje sin from_user → filtro no pasa."""
        f = AuthorizedUserFilter(mock_settings)
        msg = MagicMock()
        msg.from_user = None
        msg.message_id = 42
        assert f.filter(msg) is False


# ── AdminOnlyFilter ──────────────────────────────────────────────────────────


class TestAdminOnlyFilter:
    """Tests para AdminOnlyFilter."""

    def test_deja_pasar_admin(self, mock_settings):
        """Admin ID → AdminOnlyFilter pasa."""
        f = AdminOnlyFilter(mock_settings)
        msg = MagicMock()
        msg.from_user.id = 123456789
        assert f.filter(msg) is True

    def test_bloquea_editor(self, mock_settings):
        """Editor ID → AdminOnlyFilter no pasa."""
        f = AdminOnlyFilter(mock_settings)
        msg = MagicMock()
        msg.from_user.id = 111222333  # editor
        msg.from_user.username = "editor"
        assert f.filter(msg) is False

    def test_bloquea_desconocido(self, mock_settings):
        """Desconocido → AdminOnlyFilter no pasa."""
        f = AdminOnlyFilter(mock_settings)
        msg = MagicMock()
        msg.from_user.id = 999999999
        msg.from_user.username = "hacker"
        assert f.filter(msg) is False

    def test_bloquea_editor_con_log_warning(self, mock_settings):
        """Editor bloqueado genera log WARNING."""
        f = AdminOnlyFilter(mock_settings)
        msg = MagicMock()
        msg.from_user.id = 111222333
        msg.from_user.username = "editor"
        with patch("agents.telegram_listener.filters.log") as mock_log:
            f.filter(msg)
            mock_log.warning.assert_called_once()

    def test_bloquea_sin_usuario(self, mock_settings):
        """Mensaje sin from_user → no pasa."""
        f = AdminOnlyFilter(mock_settings)
        msg = MagicMock()
        msg.from_user = None
        assert f.filter(msg) is False

    def test_segundo_admin_pasa(self, mock_settings):
        """Segundo admin ID → AdminOnlyFilter pasa."""
        f = AdminOnlyFilter(mock_settings)
        msg = MagicMock()
        msg.from_user.id = 987654321  # segundo admin
        assert f.filter(msg) is True


# ── EditorOrAdminFilter ──────────────────────────────────────────────────────


class TestEditorOrAdminFilter:
    """Tests para EditorOrAdminFilter."""

    def test_deja_pasar_editor(self, mock_settings):
        """Editor ID → EditorOrAdminFilter pasa."""
        f = EditorOrAdminFilter(mock_settings)
        msg = MagicMock()
        msg.from_user.id = 111222333
        assert f.filter(msg) is True

    def test_deja_pasar_admin(self, mock_settings):
        """Admin ID → EditorOrAdminFilter pasa."""
        f = EditorOrAdminFilter(mock_settings)
        msg = MagicMock()
        msg.from_user.id = 123456789
        assert f.filter(msg) is True

    def test_bloquea_desconocido(self, mock_settings):
        """Desconocido → EditorOrAdminFilter no pasa."""
        f = EditorOrAdminFilter(mock_settings)
        msg = MagicMock()
        msg.from_user.id = 999999999
        assert f.filter(msg) is False

    def test_bloquea_sin_usuario(self, mock_settings):
        """Sin from_user → no pasa."""
        f = EditorOrAdminFilter(mock_settings)
        msg = MagicMock()
        msg.from_user = None
        assert f.filter(msg) is False

    def test_settings_sin_editors_solo_admin_pasa(self, mock_settings_admin_only):
        """Sin editors configurados, solo admin pasa."""
        f = EditorOrAdminFilter(mock_settings_admin_only)
        msg = MagicMock()
        msg.from_user.id = 123456789  # admin
        assert f.filter(msg) is True

    def test_settings_sin_editors_desconocido_no_pasa(self, mock_settings_admin_only):
        """Sin editors configurados, desconocido no pasa."""
        f = EditorOrAdminFilter(mock_settings_admin_only)
        msg = MagicMock()
        msg.from_user.id = 111222333  # no es admin ni editor
        assert f.filter(msg) is False
