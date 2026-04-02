"""
Management command para importar materias desde planesestudio.unsl.edu.ar.

Uso:
    python manage.py importar_materias
    python manage.py importar_materias --carrera 03062   # solo una carrera
    python manage.py importar_materias --limpiar         # borra materias antes de importar
"""

import re
import time
import urllib.request
from html.parser import HTMLParser

from django.core.management.base import BaseCommand

from horarios.models import Carrera, Materia

BASE_URL = 'http://planesestudio.unsl.edu.ar/'

# Mapa: codigo_carrera → URL relativa del plan vigente más reciente
PLANES_VIGENTES = {
    '03025': 'index.php?action=car_g3&fac=3&car=03025&plan=6/24&version=1&version_id=1206',
    '03062': 'index.php?action=car_g3&fac=3&car=03062&plan=28/12&version=3&version_id=884',
    '03061': 'index.php?action=car_g3&fac=3&car=03061&plan=2/25&version=3&version_id=1253',
    '03054': 'index.php?action=car_g3&fac=3&car=03054&plan=11/23&version=1&version_id=878',
    '16001': 'index.php?action=car_g3&fac=16&car=16001&plan=27/22&version=2&version_id=614',
    '03003': 'index.php?action=car_g3&fac=3&car=03003&plan=1/23&version=3&version_id=1248',
    '03004': 'index.php?action=car_g3&fac=3&car=03004&plan=02/22&version=5&version_id=1115',
    '03002': 'index.php?action=car_g3&fac=3&car=03002&plan=09/17&version=3&version_id=629',
    '03001': 'index.php?action=car_g3&fac=3&car=03001&plan=15/06&version=5&version_id=246',
    '03058': 'index.php?action=car_g3&fac=3&car=03058&plan=12/14&version=3&version_id=338',
    '03034': 'index.php?action=car_g3&fac=3&car=03034&plan=14/05&version=2&version_id=116',
    '03024': 'index.php?action=car_g3&fac=3&car=03024&plan=02/16&version=2&version_id=232',
    '03014': 'index.php?action=car_g3&fac=3&car=03014&plan=16/06&version=3&version_id=682',
    '03060': 'index.php?action=car_g3&fac=3&car=03060&plan=21/13&version=3&version_id=1198',
    '03027': 'index.php?action=car_g3&fac=3&car=03027&plan=5/09&version=5&version_id=248',
    '03035': 'index.php?action=car_g3&fac=3&car=03035&plan=13/05&version=2&version_id=115',
    '03TUE': 'index.php?action=car_g3&fac=3&car=03TUE&plan=15/13&version=1&version_id=178',
    '03TER': 'index.php?action=car_g3&fac=3&car=03TER&plan=05/13&version=2&version_id=327',
    '03TEM': 'index.php?action=car_g3&fac=3&car=03TEM&plan=14/13&version=2&version_id=221',
    '03063': 'index.php?action=car_g3&fac=3&car=03063&plan=15/15&version=4&version_id=866',
    '03059': 'index.php?action=car_g3&fac=3&car=03059&plan=09/13&version=3&version_id=340',
    '03TUM': 'index.php?action=car_g3&fac=3&car=03TUM&plan=4/20&version=4&version_id=1168',
    '03TOV': 'index.php?action=car_g3&fac=3&car=03TOV&plan=01/18&version=6&version_id=1234',
    '03TPM': 'index.php?action=car_g3&fac=3&car=03TPM&plan=11/13&version=3&version_id=333',
    '03053': 'index.php?action=car_g3&fac=3&car=03053&plan=12/15&version=3&version_id=1189',
    '03TUT': 'index.php?action=car_g3&fac=3&car=03TUT&plan=16/13&version=2&version_id=180',
    '03064': 'index.php?action=car_g3&fac=3&car=03064&plan=13/22&version=2&version_id=627',
    '03052': 'index.php?action=car_g3&fac=3&car=03052&plan=08/13&version=1&version_id=174',
    '03008': 'index.php?action=car_g3&fac=3&car=03008&plan=8/01&version=2&version_id=111',
}

ANO_PALABRAS = {
    'primer': 1, 'primero': 1, 'primera': 1,
    'segundo': 2, 'segunda': 2,
    'tercer': 3, 'tercero': 3, 'tercera': 3,
    'cuarto': 4, 'cuarta': 4,
    'quinto': 5, 'quinta': 5,
}


def parsear_cuatrimestre(texto):
    """Convierte un texto de período en número de cuatrimestre (1, 2 o 3=Anual)."""
    t = texto.lower().strip()
    if 'anual' in t:
        return 3  # Materia anual
    if re.search(r'2[°\.]?\s*(cuatrimestre|cuat)|2do\s*cuat', t):
        return 2
    if re.search(r'1[°\.]?\s*(cuatrimestre|cuat)|1er\s*cuat', t):
        return 1
    return 1  # default


def parsear_ano_desde_titulo(titulo):
    """Extrae el número de año desde un título como 'Materias del Tercer Año'."""
    titulo_lower = titulo.lower()
    for palabra, numero in ANO_PALABRAS.items():
        if palabra in titulo_lower:
            return numero
    return None


class PlanParser(HTMLParser):
    """Parser para extraer materias de la página de plan de estudios."""

    def __init__(self):
        super().__init__()
        self.materias = []        # lista de dicts {codigo, nombre, ano, cuatrimestre}
        self._en_tabla_ano = False
        self._ano_actual = None
        self._en_fila = False
        self._col = 0
        self._en_celda = False
        self._texto_celda = ''
        self._fila_actual = []
        self._es_optativa = False

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            # Solo resetear si estamos dentro de una tabla de año, para manejar
            # tablas anidadas. No reseteamos _ano_actual porque cada año puede
            # estar en su propia <table> y el título aparece luego del tag.
            self._en_tabla_ano = False
            self._es_optativa = False
        elif tag == 'tr':
            self._en_fila = True
            self._col = 0
            self._fila_actual = []
        elif tag in ('td', 'th'):
            self._en_celda = True
            self._texto_celda = ''

    def _procesar_celda(self, texto):
        """Detecta títulos de año u optativas en el texto de una celda."""
        texto_lower = texto.lower()
        if 'materias del' in texto_lower:
            ano = parsear_ano_desde_titulo(texto_lower)
            if ano:
                self._en_tabla_ano = True
                self._ano_actual = ano
                self._es_optativa = False
        elif 'materias optativas de' in texto_lower: #or ('optativa' in texto_lower and self._col <= 1):
            self._es_optativa = True
            self._en_tabla_ano = False

    def handle_endtag(self, tag):
        if tag in ('td', 'th'):
            self._en_celda = False
            texto = re.sub(r'\s+', ' ', self._texto_celda).strip()

            # Solo agregar a fila_actual si es <td> (datos de la tabla)
            if tag == 'td':
                self._fila_actual.append(texto)

            # Detectar encabezado de año u optativas en <td> y <th>
            self._procesar_celda(texto)

            self._col += 1

        elif tag == 'tr':
            self._en_fila = False
            # Procesar fila de datos (no encabezado) si estamos en tabla de año
            if self._en_tabla_ano and not self._es_optativa and len(self._fila_actual) >= 3:
                cod_raw = self._fila_actual[0]  # "N (CODIGO)"
                nombre = self._fila_actual[1].strip()
                periodo = self._fila_actual[2] if len(self._fila_actual) > 2 else ''

                # Extraer código entre paréntesis: "1 (03MA00194)" → "03MA00194"
                m = re.search(r'\(([^)]+)\)', cod_raw)
                codigo = m.group(1).strip() if m else cod_raw.strip()

                cuatrimestre = parsear_cuatrimestre(periodo)

                if nombre and self._ano_actual and not nombre.lower().startswith('materias'):
                    self.materias.append({
                        'codigo': codigo,
                        'nombre': nombre,
                        'ano': self._ano_actual,
                        'cuatrimestre': cuatrimestre,
                    })

        elif tag == 'table':
            self._en_tabla_ano = False

    def handle_data(self, data):
        if self._en_celda:
            self._texto_celda += data


def fetch_html(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read()
        # Intentar detectar encoding del header o usar latin-1 (típico en sitios UNSL)
        content_type = resp.headers.get_content_charset() or 'latin-1'
        return raw.decode(content_type, errors='replace')


class Command(BaseCommand):
    help = 'Importa materias de los planes vigentes desde planesestudio.unsl.edu.ar'

    def add_arguments(self, parser):
        parser.add_argument(
            '--carrera',
            type=str,
            help='Código de carrera para importar solo esa (ej: 03062)',
        )
        parser.add_argument(
            '--limpiar',
            action='store_true',
            help='Elimina todas las materias existentes antes de importar',
        )

    def handle(self, *args, **options):
        carrera_filter = options.get('carrera')
        limpiar = options.get('limpiar')

        if limpiar:
            if carrera_filter:
                count = Materia.objects.filter(carrera__codigo=carrera_filter).delete()[0]
                self.stdout.write(f'  Eliminadas {count} materias de {carrera_filter}')
            else:
                count = Materia.objects.all().delete()[0]
                self.stdout.write(f'  Eliminadas {count} materias')

        planes = PLANES_VIGENTES
        if carrera_filter:
            planes = {k: v for k, v in PLANES_VIGENTES.items() if k == carrera_filter}
            if not planes:
                self.stderr.write(f'Carrera {carrera_filter} no encontrada en el mapa de planes.')
                return

        total_creadas = 0
        total_existentes = 0

        for codigo, url_relativa in planes.items():
            try:
                carrera = Carrera.objects.get(codigo=codigo)
            except Carrera.DoesNotExist:
                self.stderr.write(f'  [SKIP] Carrera {codigo} no existe en la base de datos.')
                continue

            url = BASE_URL + url_relativa
            self.stdout.write(f'>> {carrera.nombre} ({codigo})...')

            try:
                html = fetch_html(url)
            except Exception as e:
                self.stderr.write(f'  [ERROR] No se pudo obtener {url}: {e}')
                continue

            parser = PlanParser()
            parser.feed(html)

            if not parser.materias:
                self.stdout.write(self.style.WARNING(f'  Sin materias encontradas'))
                continue

            creadas = 0
            existentes = 0
            for m in parser.materias:
                # Normalizar nombre: capitalizar palabras
                nombre = m['nombre'].title()

                obj, created = Materia.objects.get_or_create(
                    carrera=carrera,
                    codigo=m['codigo'],
                    defaults={
                        'nombre': nombre,
                        'ano': m['ano'],
                        'cuatrimestre': m['cuatrimestre'],
                    }
                )
                if created:
                    creadas += 1
                else:
                    existentes += 1

            self.stdout.write(
                self.style.SUCCESS(f'  OK: {creadas} creadas, {existentes} ya existian')
            )
            total_creadas += creadas
            total_existentes += existentes

            # Pausa para no saturar el servidor
            time.sleep(0.5)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Importación completa: {total_creadas} materias creadas, '
            f'{total_existentes} ya existían.'
        ))
