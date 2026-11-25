# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

Django web app that publishes the weekly class schedules (horarios) of the careers of the
Facultad de Ciencias Físico Matemáticas y Naturales (FCFMyN), Universidad Nacional de San Luis.
Anonymous users browse schedules; logged-in staff edit them through a custom panel (`/panel/`).

The domain, code identifiers, UI strings, templates and commit history are in **Spanish**
(Rioplatense voice: "tenés", "podés", "dejá"). Keep new user-facing text and identifiers in
Spanish and in that voice. `ano` means *año* (year of the degree); `cuatrimestre` is the semester.

## Stack

- Python 3, Django ≥ 6, single app `horarios`, project package `config`
- PostgreSQL via `dj-database-url` (`DATABASE_URL`); settings via `python-decouple` reading `.env`
- Server-rendered templates + Bootstrap 5.3 / Bootstrap Icons **from CDN** (no JS build step);
  the only local static file is `horarios/static/horarios/css/custom.css`
- `openpyxl` (Excel export), `xhtml2pdf` (PDF export), `whitenoise` + `gunicorn` for deployment on Render

## Commands

Windows dev machine; the venv lives in `venv/` (gitignored).

```bash
venv\Scripts\activate                 # PowerShell: venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate              # also creates groups + seeds careers (data migrations)
python manage.py createsuperuser
python manage.py runserver
python manage.py makemigrations horarios
python manage.py test horarios        # NOTE: horarios/tests.py is an empty stub — there are no tests yet
python manage.py collectstatic        # → staticfiles/ (served by whitenoise)

# Data commands (horarios/management/commands/)
python manage.py actualizar_carreras              # upsert careers by código, delete C01–C22 placeholders
python manage.py importar_materias                # scrape planesestudio.unsl.edu.ar for all careers
python manage.py importar_materias --carrera 03062
python manage.py importar_materias --limpiar      # DELETE existing materias first (cascades to horarios!)
```

`importar_materias` makes live HTTP requests (0.5 s pause between careers) and uses
`get_or_create` keyed on `(carrera, codigo)`, so re-running it does not update existing rows.

## Configuration

`config/settings.py` reads from `.env` (template: `.env.example`):

- `DATABASE_URL` — **required**, no default; Django will not start without it.
  The README's `DB_NAME/DB_USER/...` variables are obsolete (that block is commented out in settings).
- `SECRET_KEY`, `DEBUG` (default `True`), `ALLOWED_HOSTS` (default includes `.onrender.com`).
- `CSRF_TRUSTED_ORIGINS` is hardcoded to `https://*.onrender.com`.
- Locale `es-ar`, TZ `America/Argentina/Buenos_Aires`. Login at `/accounts/login/`, then redirect to `/panel/`.

Deployment (Render): Build Command must be `bash build.sh`, which runs pip install,
`collectstatic` and `migrate`. Start command: `gunicorn config.wsgi`. WhiteNoise only serves
what `collectstatic` put in `staticfiles/`. If that step is skipped, every `/static/` URL
returns 404: the admin loses its styles and the public site loses `custom.css`, including the calendar colors.

Never read or commit `.env`. `backup.sql` / `backup_neon.sql` are committed PostgreSQL dumps
(local and Neon), not loaded by anything; do not modify them as part of code changes.

## Data model (`horarios/models.py`)

```
Carrera (codigo unique, duracion_anos 3|4|5)
└── Materia (FK carrera; ano 1–5; cuatrimestre 1|2|3=Anual; docente FK→User, nullable)
    └── Horario (OneToOne materia; primer_dia_actividades)
        └── HorarioBloque (FK horario; dia_semana lunes..sabado; hora_inicio/fin; aula FK→Aula, nullable)
Aula (ubicacion choice, planta choice, nombre; unique together)
MateriaAsignacion (usuario, materia) unique together — which editor may edit which materia
PerfilEditor (OneToOne usuario; creado_por FK→User) — which manager created a user
```

- Exactly one `Horario` per `Materia`, accessed as `materia.horario` (raises if missing —
  views use `getattr(materia, 'horario', None)` or `hasattr`).
- `cuatrimestre == 3` (Anual) materias are shown in **both** semesters of the public calendar.
- `HorarioBloque.DIA_CHOICES` order is the canonical day order; `views.DIA_ORDER` derives from it.
  Ordering by `dia_semana` in the DB is alphabetical, so views re-sort with `DIA_ORDER`.

## Roles and permissions

Roles are Django `Group`s: `admin`, `manager`, `editor`, all created by data migrations
(0002 and 0007). Superusers count as admin. Helpers are in `horarios/decorators.py`:

| Decorator / helper | Allows |
|---|---|
| `admin_required`, `is_admin` | superuser or `admin` group |
| `manager_or_admin_required`, `is_manager_or_admin` | + `manager` |
| `editor_or_admin_required` | + `manager`, `editor` (any panel user) |

Object-level rules are enforced **inside views**, not by decorators. Preserve them when you
change or add views:

- Non-admins may only edit or delete a `Horario` when a `MateriaAsignacion(usuario=user, materia=...)`
  exists. This applies to managers too.
- Managers see, edit and delete only the users whose `PerfilEditor.creado_por` is themselves, and
  only those users' assignments. They cannot touch admins and can only grant the `editor` role
  (`ROL_CHOICES_MANAGER` in `forms.py`).
- Careers, materias and aulas CRUD is admin-only. Reports are for managers and admins.
- `aula_crear_inline` (JSON endpoint used from the schedule editor) is open to any panel user.

Side effect to keep in mind: `views._guardar_asignaciones` replaces all of a user's assignments
and **also sets `Materia.docente`** to that user for the assigned materias, clearing it on removed ones.

## Code layout and conventions

- `horarios/views.py` holds every view as a function-based view (no CBVs), grouped by section
  comments (`# ─── Reportes ───`). URL names are defined in `horarios/urls.py`; templates refer to
  them by name.
- Templates: `horarios/templates/horarios/`. Public pages sit at the top level, the staff panel
  lives under `admin_panel/<entity>/{list,form,confirm_delete}.html`, and reports under `reportes/`
  (with `reportes/pdf/` as the simplified HTML for xhtml2pdf). All extend `base.html`.
- Forms (`forms.py`) are ModelForms whose Bootstrap classes are set through widget attrs
  (`BS_INPUT`, `BS_SELECT`). `HorarioBloqueFormSet` is an inline formset with prefix `bloques`
  and `min_num=1`. `admin_panel/horario/form.html` adds rows client-side by cloning a
  `__prefix__` template and bumping `TOTAL_FORMS`, and it creates aulas through `fetch` to `aula_crear_inline`.
  Keep the field names in that template in sync with `HorarioBloqueForm`.
- Calendar layout (`carrera_detail`, `aula_detail`) is computed **server-side**: 80 px per hour
  (`_CAL_PX_PER_HOUR`), minimum block height 28 px, and colors cycle through `cal-*` CSS classes
  defined in `custom.css`. Both views duplicate this logic, so change it in both places.
- `aula_detail` merges blocks with the same day, time and materia name (the same course
  listed under several careers) into one entry.
- Reports have three variants each (HTML, `/excel/`, `/pdf/`) built from a shared `_datos_*()`
  helper. `_datos_conflictos` flags overlapping blocks in the same aula and day, **except** when both
  materias have the same `docente` (treated as a shared or merged class).
- Heavy imports (`openpyxl`, `xhtml2pdf`) happen inside the export view functions.
- `horarios/admin.py` also registers everything in the Django admin (`/admin/`).

## Known inconsistencies (don't be surprised)

- The career list is duplicated, and the copies don't match: migration `0002_initial_data`, `actualizar_carreras.CARRERAS`
  (a subset, with different durations), and `importar_materias.PLANES_VIGENTES`
  (code → plan URL). The README says there are 29 careers. Treat `actualizar_carreras` as the current source of durations.
- `MIDDLEWARE` lists `SecurityMiddleware` twice. `requirements.txt` lists both `psycopg` and
  `psycopg2-binary`, and lists `python-decouple` twice.
- The README predates `Aula`, `PerfilEditor`, reports and the `manager` scoping rules.
- `ToDos.txt` holds the backlog: accent-insensitive search, email notifications, classroom capacity.
