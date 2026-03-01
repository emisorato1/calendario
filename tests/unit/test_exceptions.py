# tests/unit/test_exceptions.py
"""Tests para la jerarquía de excepciones de dominio."""

import pytest
from src.core.exceptions import (
    AgenteCalendarioError,
    CalendarError,
    CalendarSyncError,
    ClienteNotFoundError,
    DatabaseError,
    DuplicateClienteError,
    EventoNotFoundError,
    InvalidDateError,
    LLMError,
    LLMParsingError,
    LLMUnavailableError,
    PermissionDeniedError,
    ScheduleConflictError,
)


class TestExceptionHierarchy:
    """Tests para verificar la jerarquía de excepciones."""

    def test_base_exception_message(self):
        """La excepción base tiene message y details."""
        err = AgenteCalendarioError("algo falló", details="detalle técnico")
        assert err.message == "algo falló"
        assert err.details == "detalle técnico"
        assert str(err) == "algo falló"

    def test_base_exception_default_details(self):
        """details tiene valor por defecto vacío."""
        err = AgenteCalendarioError("error simple")
        assert err.details == ""

    def test_database_errors_inherit_from_base(self):
        """Los errores de DB heredan de AgenteCalendarioError."""
        assert issubclass(DatabaseError, AgenteCalendarioError)
        assert issubclass(ClienteNotFoundError, AgenteCalendarioError)
        assert issubclass(EventoNotFoundError, AgenteCalendarioError)
        assert issubclass(DuplicateClienteError, AgenteCalendarioError)

    def test_calendar_errors_inherit_from_base(self):
        """Los errores de Calendar heredan de AgenteCalendarioError."""
        assert issubclass(CalendarError, AgenteCalendarioError)
        assert issubclass(CalendarSyncError, CalendarError)
        assert issubclass(CalendarSyncError, AgenteCalendarioError)

    def test_llm_errors_inherit_from_base(self):
        """Los errores de LLM heredan de AgenteCalendarioError."""
        assert issubclass(LLMError, AgenteCalendarioError)
        assert issubclass(LLMParsingError, LLMError)
        assert issubclass(LLMUnavailableError, LLMError)
        assert issubclass(LLMParsingError, AgenteCalendarioError)

    def test_business_errors_inherit_from_base(self):
        """Los errores de negocio heredan de AgenteCalendarioError."""
        assert issubclass(ScheduleConflictError, AgenteCalendarioError)
        assert issubclass(PermissionDeniedError, AgenteCalendarioError)
        assert issubclass(InvalidDateError, AgenteCalendarioError)

    def test_catch_all_with_base(self):
        """Se pueden capturar todos los errores con la excepción base."""
        exceptions = [
            DatabaseError("db error"),
            ClienteNotFoundError("no encontrado"),
            EventoNotFoundError("no encontrado"),
            CalendarError("cal error"),
            CalendarSyncError("sync error"),
            LLMError("llm error"),
            LLMParsingError("parse error"),
            LLMUnavailableError("unavailable"),
            ScheduleConflictError("conflicto"),
            PermissionDeniedError("sin permiso"),
            InvalidDateError("fecha inválida"),
            DuplicateClienteError("duplicado"),
        ]
        for exc in exceptions:
            with pytest.raises(AgenteCalendarioError):
                raise exc

    def test_specific_catch(self):
        """Se pueden capturar errores específicos sin capturar otros."""
        with pytest.raises(LLMParsingError):
            raise LLMParsingError("no se pudo parsear")

        # LLMParsingError no es CalendarError
        with pytest.raises(LLMParsingError):
            try:
                raise LLMParsingError("test")
            except CalendarError:
                pytest.fail("No debería capturar LLMParsingError como CalendarError")
            except LLMParsingError:
                raise

    def test_calendar_sync_error_caught_by_calendar_error(self):
        """CalendarSyncError se captura como CalendarError."""
        with pytest.raises(CalendarError):
            raise CalendarSyncError("fallo de sync")

    def test_all_exceptions_are_also_base_exceptions(self):
        """Todas las excepciones son también Exception estándar."""
        err = ScheduleConflictError("conflicto")
        assert isinstance(err, Exception)
        assert isinstance(err, AgenteCalendarioError)
        assert isinstance(err, ScheduleConflictError)
