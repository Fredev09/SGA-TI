# SGA-TI · Sistema de Gestión Ambiental

Aplicación web de apoyo a un Sistema de Gestión Ambiental bajo **ISO 14001:2015** para la empresa simulada **CloudTech Solutions S.A.S.** (sector TI/cloud).

Proyecto académico de taller de Ingeniería de Sistemas.

## Stack

- **Backend:** Django 5.2 LTS
- **Base de datos:** SQLite local (gestionada con ORM y migraciones de Django)
- **Interfaz:** monolito Django con plantillas, CSS y JS modulares
- **Zona horaria:** `America/Bogota`

## Estructura

Monolito Django con las siguientes apps:

- `core` — modelos base (identificador y versionado) y punto de entrada.
- `cuentas` — usuarios, roles (`OPERADOR`, `RESPONSABLE_SGA`), autenticación y permisos.
- `ambiental` — catálogo de procesos, aspectos e impactos e indicadores.
- `operacion` — mediciones y semáforo de estado.
- `gestion` — no conformidades, acciones correctivas y reportes.

## Requisitos

- Python 3.14
- Django 5.2

## Puesta en marcha

```bash
pip install -r sga_ti/requirements.txt
python sga_ti/manage.py migrate
python sga_ti/manage.py runserver
```

La app necesita una `SECRET_KEY` local. Crear el archivo `sga_ti/secretos_local.py` con:

```python
SECRET_KEY = "tu-clave-local"
```

Ese archivo (y la base de datos) quedan fuera del repositorio por diseño.

## Pruebas

```bash
python sga_ti/manage.py test
```

La integración continua ejecuta `manage.py check` y la suite completa en cada *push* y *pull request*.

## Roles

- **OPERADOR:** acceso restringido al tablero y registro de mediciones.
- **RESPONSABLE_SGA:** acceso total a las vistas operativas, gestión de configuración y cierre de no conformidades.

## Licencia

Proyecto académico. Todos los datos ambientales son de demostración.
