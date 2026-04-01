"""
Actualiza (o crea) las carreras reales de la FCFMyN-UNSL.
Elimina los placeholders C01-C22 si existen.

Uso:
    python manage.py actualizar_carreras
"""

from django.core.management.base import BaseCommand
from horarios.models import Carrera

CARRERAS = [
    ('03025', 'Ingeniería Electrónica con Orientación en Sistemas Digitales', 5),
    ('03062', 'Ingeniería en Computación', 5),
    ('03061', 'Ingeniería en Informática', 5),
    ('03054', 'Ingeniería en Minas', 5),
    ('16001', 'Licenciatura en Análisis y Gestión de Datos', 4),
    ('03003', 'Licenciatura en Ciencias de la Computación', 4),
    ('03004', 'Licenciatura en Ciencias Geológicas', 4),
    ('03002', 'Licenciatura en Ciencias Matemáticas', 4),
    ('03001', 'Licenciatura en Física', 4),
    ('03058', 'Licenciatura en Matemática Aplicada', 4),
    ('03034', 'Profesorado de Tercer Ciclo EGB y Educación Polimodal en Matemática', 4),
    ('03024', 'Profesorado en Ciencias de la Computación', 4),
    ('03014', 'Profesorado en Física', 4),
    ('03060', 'Profesorado en Matemática', 4),
    ('03027', 'Profesorado en Tecnología Electrónica', 4),
    ('03035', 'Profesorado Universitario en Matemáticas', 4),
    ('03TUE', 'Tecnicatura Universitaria en Electrónica', 3),
    ('03TER', 'Tecnicatura Universitaria en Energías Renovables', 3),
    ('03TEM', 'Tecnicatura Universitaria en Explotación Minera', 3),
    ('03063', 'Tecnicatura Universitaria en Fotografía', 3),
    ('03059', 'Tecnicatura Universitaria en Geoinformática', 3),
    ('03TUM', 'Tecnicatura Universitaria en Minería', 3),
    ('03TOV', 'Tecnicatura Universitaria en Obras Viales', 3),
    ('03TPM', 'Tecnicatura Universitaria en Procesamiento de Minerales', 3),
    ('03053', 'Tecnicatura Universitaria en Redes de Computadoras', 3),
    ('03TUT', 'Tecnicatura Universitaria en Telecomunicaciones', 3),
    ('03064', 'Tecnicatura Universitaria en Teledetección y Sistemas de Información Geográfica', 3),
    ('03052', 'Tecnicatura Universitaria en Web', 3),
    ('03008', 'Técnico Universitario en Microprocesadores', 3),
]


class Command(BaseCommand):
    help = 'Actualiza las carreras reales de la FCFMyN-UNSL y elimina placeholders'

    def handle(self, *args, **options):
        # Eliminar placeholders C01..C22 y cualquier carrera con código inválido
        placeholder_codigos = [f'C{str(i).zfill(2)}' for i in range(1, 23)] + \
                              [f'C{i}' for i in range(1, 23)]
        eliminadas = Carrera.objects.filter(codigo__in=placeholder_codigos).delete()[0]
        if eliminadas:
            self.stdout.write(f'  Eliminados {eliminadas} registros placeholder.')

        # Crear/actualizar carreras reales
        creadas = 0
        actualizadas = 0
        for codigo, nombre, duracion in CARRERAS:
            obj, created = Carrera.objects.update_or_create(
                codigo=codigo,
                defaults={'nombre': nombre, 'duracion_anos': duracion},
            )
            if created:
                creadas += 1
            else:
                actualizadas += 1

        self.stdout.write(self.style.SUCCESS(
            f'Carreras actualizadas: {creadas} creadas, {actualizadas} actualizadas.'
        ))
