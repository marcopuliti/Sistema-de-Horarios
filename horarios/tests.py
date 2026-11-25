import datetime
import io
import zipfile

import openpyxl
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from .models import Aula, Carrera, Horario, HorarioBloque, Materia


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
