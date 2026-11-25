import datetime
import io
import zipfile

import os
import tempfile

import openpyxl
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import Aula, Carrera, Horario, HorarioBloque, Materia, MateriaAsignacion, PerfilEditor


class ExportHorariosCarreraTests(TestCase):
    def setUp(self):
        self.carrera = Carrera.objects.create(nombre='Carrera de Prueba', codigo='TEST1', duracion_anos=3)
        self.otra = Carrera.objects.create(nombre='Otra Carrera', codigo='TEST2', duracion_anos=4)
        aula = Aula.objects.create(ubicacion='bloque_i', planta='pb', nombre='10')

        m1 = Materia.objects.create(carrera=self.carrera, nombre='Álgebra', codigo='A1', ano=1, cuatrimestre=1)
        h1 = Horario.objects.create(materia=m1, primer_dia_actividades=datetime.date(2026, 3, 9))
        HorarioBloque.objects.create(horario=h1, dia_semana='miercoles',
                                     hora_inicio=datetime.time(10), hora_fin=datetime.time(12), aula=aula)
        HorarioBloque.objects.create(horario=h1, dia_semana='lunes',
                                     hora_inicio=datetime.time(8), hora_fin=datetime.time(10))

        m3 = Materia.objects.create(carrera=self.carrera, nombre='Física Anual', ano=3, cuatrimestre=3)
        h3 = Horario.objects.create(materia=m3, primer_dia_actividades=datetime.date(2026, 3, 16))
        HorarioBloque.objects.create(horario=h3, dia_semana='viernes',
                                     hora_inicio=datetime.time(14), hora_fin=datetime.time(16))

        # Materia sin horario: no debe aparecer
        Materia.objects.create(carrera=self.carrera, nombre='Sin Horario', ano=2, cuatrimestre=2)

        self.admin = User.objects.create_user('admin1', password='x')
        self.admin.groups.add(Group.objects.get(name='admin'))
        self.manager = User.objects.create_user('manager1', password='x')
        self.manager.groups.add(Group.objects.get(name='manager'))

    def _get(self, user, url):
        self.client.force_login(user)
        return self.client.get(url)

    def test_excel_carrera_una_hoja_por_ano(self):
        resp = self._get(self.admin, reverse('reporte_horarios_carrera_excel', args=[self.carrera.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('horarios_TEST1_carrera-de-prueba.xlsx', resp['Content-Disposition'])

        wb = openpyxl.load_workbook(io.BytesIO(resp.content))
        self.assertEqual(wb.sheetnames, ['1° Año', '2° Año', '3° Año'])

        filas = list(wb['1° Año'].iter_rows(min_row=2, values_only=True))
        # Ordenadas por día: lunes antes que miércoles
        self.assertEqual([f[4] for f in filas], ['Lunes', 'Miércoles'])
        self.assertEqual(filas[1][1], 'Álgebra')
        self.assertEqual(filas[1][7], 'Bloque I – Planta baja – 10')
        self.assertEqual(filas[0][7], '—')

        self.assertEqual(wb['2° Año']['A2'].value, 'Sin horarios cargados para este año.')
        self.assertEqual(wb['3° Año']['A2'].value, 'Anual')

    def test_zip_un_excel_por_carrera(self):
        resp = self._get(self.admin, reverse('reporte_horarios_todas_zip'))
        self.assertEqual(resp.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            nombres = zf.namelist()
            self.assertEqual(len(nombres), Carrera.objects.count())
            self.assertIn('horarios_TEST2_otra-carrera.xlsx', nombres)
            wb = openpyxl.load_workbook(io.BytesIO(zf.read('horarios_TEST2_otra-carrera.xlsx')))
            self.assertEqual(len(wb.sheetnames), 4)

    def test_botones_en_panel(self):
        url_excel = reverse('reporte_horarios_carrera_excel', args=[self.carrera.pk])
        url_zip = reverse('reporte_horarios_todas_zip')
        for pagina in ('reporte_index', 'carrera_list_panel'):
            resp = self._get(self.admin, reverse(pagina))
            self.assertContains(resp, url_excel)
            self.assertContains(resp, url_zip)
        # El manager ve reportes, pero no la tarjeta de exportación
        self.assertNotContains(self._get(self.manager, reverse('reporte_index')), url_zip)

    def test_solo_admin(self):
        for url in (reverse('reporte_horarios_todas_zip'),
                    reverse('reporte_horarios_carrera_excel', args=[self.carrera.pk])):
            self.assertEqual(self._get(self.manager, url).status_code, 403)


class ImportarDocentesTests(TestCase):
    def setUp(self):
        self.carrera = Carrera.objects.create(nombre='Ingeniería de Prueba', codigo='TEST9', duracion_anos=5)
        self.algebra = Materia.objects.create(carrera=self.carrera, nombre='Álgebra Lineal', ano=1, cuatrimestre=1)
        self.fisica = Materia.objects.create(carrera=self.carrera, nombre='Física I', ano=1, cuatrimestre=2)
        self.tmpdir = tempfile.mkdtemp()

    def _excel(self, filas, encabezado=('Carrera', 'Materia', 'Docente', 'Correo')):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['Listado de docentes 2026'])  # título antes del encabezado
        ws.append(list(encabezado))
        for f in filas:
            ws.append(list(f))
        ruta = os.path.join(self.tmpdir, 'docentes.xlsx')
        wb.save(ruta)
        return ruta

    def _importar(self, ruta, *args):
        out = io.StringIO()
        call_command('importar_docentes', ruta, *args, stdout=out)
        return out.getvalue()

    def test_crea_cuentas_y_asigna_materias(self):
        ruta = self._excel([
            # nombres sin acentos / con otras mayúsculas, y código de carrera en vez de nombre
            ('ingenieria de prueba', 'ALGEBRA LINEAL', 'Pérez, Ana', ' Ana.Perez@Example.com '),
            ('TEST9', 'fisica i', 'Pérez, Ana', 'ana.perez@example.com'),
            ('Ingeniería de Prueba', 'Materia Inexistente', 'Juan Gómez', 'juan@example.com'),
            ('Carrera Inexistente', 'Física I', 'Juan Gómez', 'juan@example.com'),
            ('TEST9', 'Física I', 'Sin Mail', 'no-es-un-mail'),
        ])
        salida = self._importar(ruta)

        ana = User.objects.get(username='ana.perez@example.com')
        self.assertEqual(ana.email, 'ana.perez@example.com')
        self.assertEqual((ana.first_name, ana.last_name), ('Ana', 'Pérez'))
        self.assertTrue(ana.check_password('ana.perez@example.com'))
        self.assertTrue(ana.groups.filter(name='editor').exists())
        self.assertTrue(PerfilEditor.objects.filter(usuario=ana).exists())
        self.assertEqual(
            set(MateriaAsignacion.objects.filter(usuario=ana).values_list('materia_id', flat=True)),
            {self.algebra.pk, self.fisica.pk},
        )
        self.algebra.refresh_from_db()
        self.assertEqual(self.algebra.docente, ana)

        self.assertFalse(User.objects.filter(username='juan@example.com').exists())
        self.assertIn('no encontré la materia "Materia Inexistente"', salida)
        self.assertIn('no encontré la carrera "Carrera Inexistente"', salida)
        self.assertIn('correo inválido', salida)

    def test_reimportar_no_duplica_ni_cambia_password(self):
        ruta = self._excel([('TEST9', 'Física I', 'Ana Pérez', 'ana@example.com')])
        self._importar(ruta)
        ana = User.objects.get(username='ana@example.com')
        ana.set_password('NuevaClaveSegura123')
        ana.save()

        self._importar(ruta)
        ana.refresh_from_db()
        self.assertTrue(ana.check_password('NuevaClaveSegura123'))
        self.assertEqual(User.objects.filter(email='ana@example.com').count(), 1)
        self.assertEqual(MateriaAsignacion.objects.filter(usuario=ana).count(), 1)

    def test_dry_run_no_guarda(self):
        ruta = self._excel([('TEST9', 'Física I', 'Ana Pérez', 'ana@example.com')])
        salida = self._importar(ruta, '--dry-run')
        self.assertIn('MODO PRUEBA', salida)
        self.assertFalse(User.objects.filter(username='ana@example.com').exists())
        self.assertFalse(MateriaAsignacion.objects.exists())


class CambioPasswordObligatorioTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('doc@example.com', email='doc@example.com',
                                             password='doc@example.com')
        self.user.groups.add(Group.objects.get(name='editor'))

    def test_con_password_inicial_obliga_a_cambiarla(self):
        self.client.post(reverse('login'), {'username': 'doc@example.com', 'password': 'doc@example.com'})
        resp = self.client.get(reverse('panel_dashboard'))
        self.assertRedirects(resp, reverse('password_change'))
        self.assertContains(self.client.get(reverse('password_change')), 'contraseña inicial')

        # No acepta una nueva contraseña parecida al email
        resp = self.client.post(reverse('password_change'), {
            'old_password': 'doc@example.com',
            'new_password1': 'doc@example.com', 'new_password2': 'doc@example.com',
        })
        self.assertEqual(resp.status_code, 200)

        resp = self.client.post(reverse('password_change'), {
            'old_password': 'doc@example.com',
            'new_password1': 'Horarios-2026-Seguro', 'new_password2': 'Horarios-2026-Seguro',
        })
        self.assertRedirects(resp, reverse('panel_dashboard'))
        self.assertEqual(self.client.get(reverse('panel_dashboard')).status_code, 200)

    def test_con_password_propia_no_redirige(self):
        self.user.set_password('OtraClave-Distinta-99')
        self.user.save()
        self.client.post(reverse('login'), {'username': 'doc@example.com', 'password': 'OtraClave-Distinta-99'})
        self.assertEqual(self.client.get(reverse('panel_dashboard')).status_code, 200)


class PlantillaDocentesTests(TestCase):
    def test_plantilla_completada_se_importa(self):
        carrera = Carrera.objects.create(nombre='Carrera Plantilla', codigo='TPL01', duracion_anos=5)
        opt1 = Materia.objects.create(carrera=carrera, nombre='Optativa', ano=4, cuatrimestre=1)
        opt2 = Materia.objects.create(carrera=carrera, nombre='Optativa', ano=5, cuatrimestre=1)
        Materia.objects.create(carrera=carrera, nombre='Química', ano=1, cuatrimestre=1)

        ruta = os.path.join(tempfile.mkdtemp(), 'plantilla.xlsx')
        call_command('plantilla_docentes', ruta, '--carrera', 'TPL01', stdout=io.StringIO())

        wb = openpyxl.load_workbook(ruta)
        self.assertEqual(wb.sheetnames, ['Docentes', 'Instrucciones'])
        ws = wb['Docentes']
        encabezados = [c.value for c in ws[1]]
        self.assertEqual(encabezados[0], 'ID materia')
        self.assertEqual(ws.max_row, 4)  # encabezado + 3 materias

        # Completar solo la Optativa de 5° año; el resto queda en blanco
        for fila in ws.iter_rows(min_row=2):
            if fila[0].value == opt2.pk:
                fila[6].value = 'Gómez, Laura'
                fila[7].value = 'laura@example.com'
        wb.save(ruta)

        salida = io.StringIO()
        call_command('importar_docentes', ruta, stdout=salida)
        laura = User.objects.get(username='laura@example.com')
        self.assertEqual(
            list(MateriaAsignacion.objects.filter(usuario=laura).values_list('materia_id', flat=True)),
            [opt2.pk],
        )
        self.assertNotIn(opt1.pk, MateriaAsignacion.objects.values_list('materia_id', flat=True))
        self.assertNotIn('Filas no procesadas', salida.getvalue())
