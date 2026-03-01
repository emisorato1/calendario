# ⚙️ Config & Observability — Configuración y Monitoreo

Módulo transversal de configuración centralizada, logging estructurado,
manejo de excepciones globales y buenas prácticas operacionales.

## Propósito

Proveer una base sólida de configuración y observabilidad que permita
diagnosticar problemas rápidamente, mantener el sistema seguro y facilitar
el despliegue en producción.

## Casos de Uso

- **Configuración centralizada**: Un solo punto de verdad para todas las
  variables del sistema (`config.py` con Pydantic Settings).
- **Logging estructurado**: Logs con rotación, niveles, timestamps y contexto.
- **Manejo de excepciones**: Excepciones de dominio tipadas y handler global.
- **Variables de entorno**: Separación clara entre dev, staging y producción.
- **Validación al inicio**: Verificar que todas las variables requeridas
  estén presentes antes de arrancar.

## Tecnología

- `pydantic-settings` para configuración tipada.
- `logging` de la stdlib con `RotatingFileHandler`.
- `python-dotenv` para cargar `.env`.

## Patrones

- **Settings Pattern**: Singleton de configuración validado con Pydantic.
- **Structured Logging**: Formato consistente para facilitar grep/parsing.
- **Exception Hierarchy**: Excepciones de dominio que extienden una base común.
- **Fail-Fast on Boot**: Si falta config crítica, no arrancar.

## Anti-patrones a Evitar

- ❌ Leer variables de entorno directamente con `os.getenv()` en cada módulo.
- ❌ Imprimir con `print()` en lugar de usar el logger.
- ❌ Silenciar excepciones con `except: pass`.
- ❌ Logs sin contexto (sin module, user_id, evento_id).
- ❌ Secrets en logs (tokens, API keys, contraseñas).

## Referencias

- [Configuración con Pydantic](references/pydantic-settings.md)
- [Logging Setup](references/logging-setup.md)
- [Excepciones de Dominio](references/domain-exceptions.md)
