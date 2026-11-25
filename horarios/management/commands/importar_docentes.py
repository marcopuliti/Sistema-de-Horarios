"""
Crea cuentas de docentes (rol editor) a partir de un Excel y las vincula a sus materias.

El Excel debe tener una fila de encabezados con las columnas (en cualquier orden,
sin importar mayúsculas ni acentos):

    Carrera | Materia | Docente | Correo

- Carrera: nombre o código de la carrera.
- Materia: nombre de la materia dentro de esa carrera.
- Docente: "Nombre Apellido" o "Apellido, Nombre".
- Correo: email del docente. Se usa como usuario y como contraseña inicial;
  al ingresar por primera vez el sistema le obliga a cambiarla.

Columnas opcionales:
- ID materia: si está, identifica la materia exactamente (la genera `plantilla_docentes`).
- Año: desempata materias con el mismo nombre dentro de una carrera.

Las filas sin docente ni correo se ignoran. Un mismo docente puede aparecer en varias
filas (una por materia) y una materia puede repetirse con distintos docentes. Si la
cuenta ya existe no se toca su contraseña: solo se agregan las materias nuevas.

Uso:
    python manage.py importar_docentes docentes.xlsx --dry-run   # solo muestra qué haría
    python manage.py importar_docentes docentes.xlsx
    python manage.py importar_docentes docentes.xlsx --hoja "Hoja1" --creado-por admin
"""

import re
import unicodedata

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction

from horarios.models import Carrera, Materia, MateriaAsignacion, PerfilEditor

COLUMNAS = {
    'carrera': {'carrera'},
    'materia': {'materia', 'asignatura'},
    'docente': {'docente', 'profesor', 'profesora', 'nombre', 'nombre y apellido', 'apellido y nombre'},
    'correo':  {'correo', 'email', 'e-mail', 'mail', 'correo electronico'},
}
COLUMNAS_OPCIONALES = {
    'id':  {'id materia', 'id'},
    'ano': {'ano'},
}


def parsear_entero(valor):
    """'3', 3.0 o '3° Año' → 3; None si no hay número."""
    m = re.search(r'\d+', str(valor or ''))
    return int(m.group()) if m else None


def normalizar(texto):
    """Minúsculas, sin acentos y con espacios colapsados, para comparar nombres."""
    texto = unicodedata.normalize('NFKD', str(texto or ''))
    texto = ''.join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', texto).strip().lower()


def separar_nombre(nombre):
    """'Apellido, Nombre' → (Nombre, Apellido); sin coma queda todo como nombre."""
    nombre = re.sub(r'\s+', ' ', nombre or '').strip()
    if ',' in nombre:
        apellido, _, nombres = nombre.partition(',')
        return nombres.strip()[:150], apellido.strip()[:150]
    return nombre[:150], ''


class Command(BaseCommand):
    help = 'Crea cuentas de docentes desde un Excel (carrera, materia, docente, correo) y les asigna sus materias'

    def add_arguments(self, parser):
        parser.add_argument('archivo', help='Ruta al archivo .xlsx')
        parser.add_argument('--hoja', help='Nombre de la hoja a leer (por defecto, la primera)')
        parser.add_argument('--creado-por', help='Username del admin/manager que figura como creador de las cuentas')
        parser.add_argument('--dry-run', action='store_true', help='Muestra lo que haría sin guardar nada')

    # ── Lectura del Excel ────────────────────────────────────────────────────

    def _leer_filas(self, archivo, hoja):
        import openpyxl
        try:
            wb = openpyxl.load_workbook(archivo, read_only=True, data_only=True)
        except Exception as e:
            raise CommandError(f'No se pudo abrir {archivo}: {e}')
        if hoja and hoja not in wb.sheetnames:
            raise CommandError(f'La hoja "{hoja}" no existe. Hojas: {", ".join(wb.sheetnames)}')
        ws = wb[hoja] if hoja else wb.worksheets[0]
        filas = list(ws.iter_rows(values_only=True))

        todas = {**COLUMNAS, **COLUMNAS_OPCIONALES}
        for i, fila in enumerate(filas[:10]):
            indices = {}
            for col, valor in enumerate(fila):
                for campo, alias in todas.items():
                    if normalizar(valor) in alias and campo not in indices:
                        indices[campo] = col
            if all(campo in indices for campo in COLUMNAS):
                datos = []
                for n, f in enumerate(filas[i + 1:], start=i + 2):
                    valores = {c: (f[idx] if idx < len(f) else None) for c, idx in indices.items()}
                    valores = {c: str(v).strip() if v is not None else '' for c, v in valores.items()}
                    valores.setdefault('id', '')
                    valores.setdefault('ano', '')
                    # Filas de la plantilla que quedaron sin completar
                    if valores['docente'] or valores['correo']:
                        datos.append((n, valores))
                return datos

        raise CommandError(
            'No encontré la fila de encabezados. Tiene que haber columnas '
            '"Carrera", "Materia", "Docente" y "Correo".'
        )

    # ── Proceso principal ────────────────────────────────────────────────────

    def handle(self, *args, **options):
        filas = self._leer_filas(options['archivo'], options.get('hoja'))
        dry_run = options['dry_run']

        creado_por = None
        if options.get('creado_por'):
            creado_por = User.objects.filter(username=options['creado_por']).first()
            if creado_por is None:
                raise CommandError(f'No existe el usuario "{options["creado_por"]}".')

        try:
            grupo_editor = Group.objects.get(name='editor')
        except Group.DoesNotExist:
            raise CommandError('No existe el grupo "editor". ¿Corriste las migraciones?')

        carreras = {}
        for c in Carrera.objects.all():
            carreras[normalizar(c.nombre)] = c
            carreras[normalizar(c.codigo)] = c
        materias_por_carrera = {}
        materias_por_id = {}
        for m in Materia.objects.select_related('docente', 'carrera'):
            materias_por_carrera.setdefault(m.carrera_id, {}).setdefault(normalizar(m.nombre), []).append(m)
            materias_por_id[m.pk] = m

        problemas = []
        avisos = []
        usuarios_nuevos, usuarios_existentes = set(), set()
        asignaciones_nuevas = 0
        docente_por_materia = {}  # materia_id → email, para detectar materias con 2 docentes

        with transaction.atomic():
            for n, fila in filas:
                email = fila['correo'].lower()
                if not email:
                    problemas.append(f'Fila {n}: falta el correo de "{fila["docente"]}".')
                    continue
                try:
                    validate_email(email)
                except ValidationError:
                    problemas.append(f'Fila {n}: correo inválido "{fila["correo"]}".')
                    continue

                materia, error = self._buscar_materia(fila, carreras, materias_por_carrera, materias_por_id)
                if error:
                    problemas.append(f'Fila {n}: {error}')
                    continue
                carrera = materia.carrera

                usuario, error = self._obtener_o_crear_usuario(email, fila['docente'], grupo_editor, creado_por)
                if error:
                    problemas.append(f'Fila {n}: {error}')
                    continue
                (usuarios_nuevos if usuario._creado else usuarios_existentes).add(email)

                _, creada = MateriaAsignacion.objects.get_or_create(usuario=usuario, materia=materia)
                asignaciones_nuevas += creada

                anterior = docente_por_materia.get(materia.pk)
                if anterior and anterior != email:
                    avisos.append(
                        f'Fila {n}: "{materia.nombre}" ({carrera.codigo}) ya tenía a {anterior} en este Excel; '
                        f'ambos quedan asignados y {email} queda como docente principal.'
                    )
                elif materia.docente_id and materia.docente_id != usuario.pk and not anterior:
                    avisos.append(
                        f'Fila {n}: "{materia.nombre}" ({carrera.codigo}) tenía como docente a '
                        f'{materia.docente.username}; se reemplaza por {email}.'
                    )
                docente_por_materia[materia.pk] = email
                materia.docente = usuario
                materia.save(update_fields=['docente'])

            if dry_run:
                transaction.set_rollback(True)

        self._resumen(len(filas), usuarios_nuevos, usuarios_existentes, asignaciones_nuevas,
                      avisos, problemas, dry_run)

    def _buscar_materia(self, fila, carreras, materias_por_carrera, materias_por_id):
        """Devuelve (materia, None) o (None, mensaje de error)."""
        carrera = carreras.get(normalizar(fila['carrera'])) if fila['carrera'] else None

        id_materia = parsear_entero(fila['id'])
        if id_materia is not None:
            materia = materias_por_id.get(id_materia)
            if materia is None:
                return None, f'no existe la materia con ID {id_materia}.'
            if carrera is not None and carrera.pk != materia.carrera_id:
                return None, (f'el ID {id_materia} es "{materia.nombre}" de {materia.carrera.nombre}, '
                              f'pero la fila dice carrera "{fila["carrera"]}".')
            return materia, None

        if carrera is None:
            return None, f'no encontré la carrera "{fila["carrera"]}".'
        candidatas = materias_por_carrera.get(carrera.pk, {}).get(normalizar(fila['materia']), [])
        ano = parsear_entero(fila['ano'])
        if len(candidatas) > 1 and ano is not None:
            candidatas = [m for m in candidatas if m.ano == ano]
        if not candidatas:
            return None, f'no encontré la materia "{fila["materia"]}" en {carrera.nombre}.'
        if len(candidatas) > 1:
            detalle = ', '.join(f'{m.ano}° año' for m in candidatas)
            return None, (f'hay {len(candidatas)} materias "{fila["materia"]}" en {carrera.nombre} '
                          f'({detalle}); indicá el ID de materia o el año.')
        return candidatas[0], None

    def _obtener_o_crear_usuario(self, email, nombre_docente, grupo_editor, creado_por):
        usuario = User.objects.filter(username__iexact=email).first()
        if usuario is None:
            por_email = list(User.objects.filter(email__iexact=email)[:2])
            if len(por_email) > 1:
                return None, f'hay más de una cuenta con el correo {email}; resolvelo a mano.'
            usuario = por_email[0] if por_email else None

        if usuario is not None:
            usuario._creado = False
            # Cuenta sin rol: la habilitamos como editor
            if not usuario.is_superuser and not usuario.groups.exists():
                usuario.groups.add(grupo_editor)
            return usuario, None

        nombre, apellido = separar_nombre(nombre_docente)
        usuario = User(username=email, email=email, first_name=nombre, last_name=apellido)
        usuario.set_password(email)
        usuario.save()
        usuario.groups.add(grupo_editor)
        PerfilEditor.objects.create(usuario=usuario, creado_por=creado_por)
        usuario._creado = True
        return usuario, None

    def _resumen(self, total, nuevos, existentes, asignaciones, avisos, problemas, dry_run):
        out = self.stdout
        out.write('')
        if dry_run:
            out.write(self.style.WARNING('MODO PRUEBA (--dry-run): no se guardó nada.'))
        out.write(f'Filas leídas:              {total}')
        out.write(self.style.SUCCESS(f'Cuentas nuevas:            {len(nuevos)}'))
        out.write(f'Cuentas ya existentes:     {len(existentes)}')
        out.write(self.style.SUCCESS(f'Asignaciones nuevas:       {asignaciones}'))
        if avisos:
            out.write('')
            out.write(self.style.WARNING(f'Avisos ({len(avisos)}):'))
            for a in avisos:
                out.write(f'  - {a}')
        if problemas:
            out.write('')
            out.write(self.style.ERROR(f'Filas no procesadas ({len(problemas)}):'))
            for p in problemas:
                out.write(f'  - {p}')
