"""
Genera la planilla para cargar docentes, con todas las materias de la base ya listadas.
Se completa Docente y Correo y se importa con `importar_docentes`.

Uso:
    python manage.py plantilla_docentes plantilla_docentes.xlsx
    python manage.py plantilla_docentes plantilla.xlsx --carrera 03062
"""

from django.core.management.base import BaseCommand, CommandError

from horarios.models import Materia

COLUMNAS = [
    # (encabezado, ancho, editable)
    ('ID materia',   11, False),
    ('Carrera',      48, False),
    ('Código',        9, False),
    ('Año',           8, False),
    ('Cuatrimestre', 16, False),
    ('Materia',      50, False),
    ('Docente',      34, True),
    ('Correo',       36, True),
]

INSTRUCCIONES = [
    ('Cómo completar esta planilla', True),
    ('', False),
    ('1. En la hoja "Docentes" completá las columnas amarillas: Docente y Correo.', False),
    ('2. Docente: "Apellido, Nombre" (con coma) o "Nombre Apellido".', False),
    ('3. Correo: será el usuario y la contraseña inicial del docente. '
     'Al ingresar por primera vez el sistema le pide cambiarla.', False),
    ('4. Si un docente dicta varias materias, escribí el mismo correo en cada una: se crea una sola cuenta.', False),
    ('5. Si una materia tiene más de un docente, copiá la fila completa (con su ID) '
     'y poné el otro docente en la copia.', False),
    ('6. Las materias que no tengan docente se dejan en blanco y se ignoran.', False),
    ('', False),
    ('No modifiques las columnas grises (ID materia, Carrera, Código, Año, Cuatrimestre, Materia): '
     'el ID es lo que identifica a cada materia.', True),
    ('Podés ordenar y filtrar libremente, pero no cambies los encabezados de la fila 1.', False),
    ('Si una materia no aparece en la lista, primero hay que darla de alta en el sistema.', False),
]


class Command(BaseCommand):
    help = 'Genera la planilla Excel para cargar docentes con todas las materias de la base'

    def add_arguments(self, parser):
        parser.add_argument('archivo', help='Ruta del .xlsx a generar')
        parser.add_argument('--carrera', help='Código de carrera para incluir solo esa')

    def handle(self, *args, **options):
        import openpyxl
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
        from openpyxl.worksheet.datavalidation import DataValidation

        materias = Materia.objects.select_related('carrera', 'docente').order_by(
            'carrera__nombre', 'ano', 'cuatrimestre', 'nombre'
        )
        if options.get('carrera'):
            materias = materias.filter(carrera__codigo=options['carrera'])
            if not materias.exists():
                raise CommandError(f'No hay materias para la carrera {options["carrera"]}.')

        fill_header = PatternFill('solid', fgColor='343A40')
        fill_fija = PatternFill('solid', fgColor='F1F3F5')
        fill_editable = PatternFill('solid', fgColor='FFF3BF')
        font_header = Font(bold=True, color='FFFFFF')
        font_fija = Font(color='495057')

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Docentes'
        ws.append([c[0] for c in COLUMNAS])
        for col, (_, ancho, _) in enumerate(COLUMNAS, start=1):
            celda = ws.cell(row=1, column=col)
            celda.font = font_header
            celda.fill = fill_header
            celda.alignment = Alignment(vertical='center')
            ws.column_dimensions[get_column_letter(col)].width = ancho

        n = 0
        for m in materias:
            docente = m.docente
            ws.append([
                m.pk,
                m.carrera.nombre,
                m.carrera.codigo,
                m.ano,
                m.get_cuatrimestre_display(),
                m.nombre,
                (f'{docente.last_name}, {docente.first_name}' if docente and docente.last_name
                 else (docente.get_full_name() if docente else None)),
                docente.email if docente else None,
            ])
            n += 1
            for col, (_, _, editable) in enumerate(COLUMNAS, start=1):
                celda = ws.cell(row=ws.max_row, column=col)
                celda.fill = fill_editable if editable else fill_fija
                if not editable:
                    celda.font = font_fija

        ultima = ws.max_row
        ws.freeze_panes = 'A2'
        ws.auto_filter.ref = f'A1:{get_column_letter(len(COLUMNAS))}{ultima}'

        # Aviso en Excel si el correo no tiene forma de email
        col_correo = get_column_letter(len(COLUMNAS))
        dv = DataValidation(
            type='custom',
            formula1=f'AND(ISNUMBER(SEARCH("@",{col_correo}2)),ISNUMBER(SEARCH(".",{col_correo}2)),'
                     f'ISERROR(SEARCH(" ",{col_correo}2)))',
            allow_blank=True,
            showErrorMessage=True,
            errorStyle='warning',
            errorTitle='Correo inválido',
            error='El correo no parece válido (debe tener @ y un dominio, sin espacios).',
        )
        dv.add(f'{col_correo}2:{col_correo}{max(ultima, 2000)}')
        ws.add_data_validation(dv)

        ins = wb.create_sheet('Instrucciones')
        ins.column_dimensions['A'].width = 120
        for texto, negrita in INSTRUCCIONES:
            ins.append([texto])
            celda = ins.cell(row=ins.max_row, column=1)
            celda.alignment = Alignment(wrap_text=True, vertical='top')
            if negrita:
                celda.font = Font(bold=True, size=12 if ins.max_row == 1 else 11)

        try:
            wb.save(options['archivo'])
        except PermissionError:
            raise CommandError(f'No se pudo guardar {options["archivo"]}: ¿está abierto en Excel?')

        self.stdout.write(self.style.SUCCESS(f'Plantilla generada: {options["archivo"]} ({n} materias)'))
