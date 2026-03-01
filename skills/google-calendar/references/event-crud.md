# CRUD de Eventos en Google Calendar

## Wrapper de Google Calendar

```python
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Optional
import logging

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]
TIMEZONE = "America/Argentina/Buenos_Aires"


class GoogleCalendarClient:
    """Wrapper simplificado de Google Calendar API."""

    def __init__(self, service_account_path: str, calendar_id: str):
        self.calendar_id = calendar_id
        credentials = service_account.Credentials.from_service_account_file(
            service_account_path, scopes=SCOPES
        )
        self.service = build("calendar", "v3", credentials=credentials)

    def create_event(
        self,
        title: str,
        location: str,
        description: str,
        start_datetime: datetime,
        duration_minutes: int = 60,
        color_id: str = "8",
    ) -> str:
        """
        Crea un evento en Google Calendar.
        
        Returns:
            ID del evento creado.
        """
        end_datetime = start_datetime + timedelta(minutes=duration_minutes)

        event_body = {
            "summary": title,
            "location": location,
            "description": description,
            "start": {
                "dateTime": start_datetime.isoformat(),
                "timeZone": TIMEZONE,
            },
            "end": {
                "dateTime": end_datetime.isoformat(),
                "timeZone": TIMEZONE,
            },
            "colorId": color_id,
        }

        event = self.service.events().insert(
            calendarId=self.calendar_id,
            body=event_body,
        ).execute()

        logger.info(f"Evento creado: {event['id']} - {title}")
        return event["id"]

    def update_event(
        self,
        event_id: str,
        **updates,
    ) -> bool:
        """Actualiza campos de un evento existente."""
        try:
            event = self.service.events().get(
                calendarId=self.calendar_id,
                eventId=event_id,
            ).execute()

            for key, value in updates.items():
                if key in ("start_datetime", "end_datetime"):
                    dt_key = "start" if "start" in key else "end"
                    event[dt_key] = {
                        "dateTime": value.isoformat(),
                        "timeZone": TIMEZONE,
                    }
                elif key == "color_id":
                    event["colorId"] = value
                else:
                    event[key] = value

            self.service.events().update(
                calendarId=self.calendar_id,
                eventId=event_id,
                body=event,
            ).execute()

            logger.info(f"Evento actualizado: {event_id}")
            return True

        except Exception as e:
            logger.error(f"Error actualizando evento {event_id}: {e}")
            return False

    def delete_event(self, event_id: str) -> bool:
        """Elimina un evento del calendario."""
        try:
            self.service.events().delete(
                calendarId=self.calendar_id,
                eventId=event_id,
            ).execute()
            logger.info(f"Evento eliminado: {event_id}")
            return True
        except Exception as e:
            logger.error(f"Error eliminando evento {event_id}: {e}")
            return False

    def list_upcoming_events(self, max_results: int = 50) -> list[dict]:
        """Lista eventos futuros."""
        now = datetime.now(ZoneInfo(TIMEZONE)).isoformat()
        events_result = self.service.events().list(
            calendarId=self.calendar_id,
            timeMin=now,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        return events_result.get("items", [])
```

## Notas

- La API de Google Calendar no es async nativa; considerar
  `asyncio.to_thread()` para no bloquear el event loop.
- El `calendar_id` viene de `.env`, no se hardcodea.
- Siempre loguear operaciones para auditoría.
