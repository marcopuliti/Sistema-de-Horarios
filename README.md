# Sistema de Horarios – FCFMyN UNSL

Aplicación web para gestionar y publicar los horarios de cursado de las 29 carreras de la **Facultad de Ciencias Físico Matemáticas y Naturales** de la Universidad Nacional de San Luis.

## Stack tecnológico

- **Backend:** Python 3 + Django 6
- **Base de datos:** PostgreSQL (psycopg3)
- **Frontend:** Bootstrap 5 + Bootstrap Icons
- **Configuración:** python-decouple (`.env`)

---

## Roles de usuario

| Rol | Acceso |
|---|---|
| **Superuser / Admin** | CRUD completo sobre carreras, materias, horarios, usuarios y asignaciones |
| **Manager** | Crear usuarios editores y asignarles materias |
| **Editor** | Modificar únicamente los horarios de las materias que tiene asignadas |
| **Anónimo** | Vista pública de horarios (solo lectura) |

---

## Instalación

### 1. Clonar el repositorio y crear el entorno virtual

```bash
git clone <url-del-repo>
cd "Sistema de Horarios"
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac
pip install -r requirements.txt
```

### 2. Configurar variables de entorno

Crear un archivo `.env` en la raíz del proyecto:

```env
SECRET_KEY=tu_clave_secreta_aqui
DEBUG=True
DB_NAME=horarios_db
DB_USER=postgres
DB_PASSWORD=tu_password
DB_HOST=localhost
DB_PORT=5432
```

### 3. Crear la base de datos PostgreSQL

```sql
CREATE DATABASE horarios_db;
```

### 4. Aplicar migraciones

```bash
python manage.py migrate
```

Esto crea las tablas y los grupos de permisos (`admin`, `manager`, `editor`) además de cargar las 29 carreras de la facultad.

### 5. Crear superusuario

```bash
python manage.py createsuperuser
```

### 6. Importar materias

```bash
python manage.py importar_materias
```

Scrapea los planes de estudio vigentes desde `planesestudio.unsl.edu.ar` e importa las materias de las 29 carreras (~699 materias en total).

### 7. Iniciar el servidor

```bash
python manage.py runserver
```

---

## Estructura del proyecto

```
Sistema de Horarios/
├── config/                    # Configuración Django
│   ├── settings.py
│   └── urls.py
├── horarios/                  # App principal
│   ├── models.py              # Modelos de datos
│   ├── views.py               # Vistas
│   ├── forms.py               # Formularios
│   ├── urls.py                # URLs
│   ├── decorators.py          # Control de acceso por rol
│   ├── admin.py               # Panel de administración Django
│   ├── migrations/            # Migraciones de base de datos
│   ├── management/commands/   # Comandos de gestión
│   │   ├── actualizar_carreras.py
│   │   └── importar_materias.py
│   ├── templates/horarios/
│   │   ├── base.html
│   │   ├── home.html
│   │   ├── carrera_detail.html        # Vista pública del calendario
│   │   └── admin_panel/
│   │       ├── dashboard.html
│   │       ├── carrera/
│   │       ├── materia/
│   │       ├── horario/
│   │       ├── usuario/
│   │       └── asignacion/
│   └── static/horarios/
└── requirements.txt
```

---

## Modelos

```
Carrera
└── Materia (ForeignKey → Carrera)
    └── Horario (OneToOne → Materia)
        └── HorarioBloque (ForeignKey → Horario)
            └── dia_semana, hora_inicio, hora_fin, aula

MateriaAsignacion (usuario, materia)  ← vincula editores con sus materias
```

- Cada materia tiene **un único Horario**.
- Un Horario puede tener **múltiples HorarioBloque** (ej: lunes y miércoles en distintas aulas).
- Las materias con `cuatrimestre = 3` son **anuales** y aparecen en ambos cuatrimestres de la vista pública.

---

## URLs principales

| URL | Descripción |
|---|---|
| `/` | Listado de carreras (vista pública) |
| `/carrera/<pk>/` | Calendario semanal de una carrera (vista pública) |
| `/panel/` | Dashboard según el rol del usuario |
| `/panel/horarios/` | Gestión de horarios por carrera/año/cuatrimestre |
| `/panel/usuarios/` | Gestión de usuarios editores (admin/manager) |
| `/panel/asignaciones/` | Asignación de materias a editores (admin/manager) |
| `/panel/carreras/` | ABM de carreras (admin) |
| `/panel/materias/` | ABM de materias (admin) |
| `/admin/` | Panel de administración de Django |

---

## Comandos de gestión

```bash
# Actualizar datos de las 29 carreras (códigos y duraciones)
python manage.py actualizar_carreras

# Importar materias desde planesestudio.unsl.edu.ar
python manage.py importar_materias
```

---

## Asignar roles a usuarios existentes

Desde el shell de Django:

```bash
python manage.py shell
```

```python
from django.contrib.auth.models import User, Group

user = User.objects.get(username='nombre_usuario')

# Asignar como admin
user.groups.add(Group.objects.get(name='admin'))

# Asignar como manager
user.groups.add(Group.objects.get(name='manager'))

# Asignar como editor
user.groups.add(Group.objects.get(name='editor'))
```

También se puede hacer desde `/admin/` → Auth → Users.
