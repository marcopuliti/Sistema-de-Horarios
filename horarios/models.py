from django.db import models
from django.conf import settings


class Carrera(models.Model):
    DURACION_CHOICES = [(3, '3 años'), (4, '4 años'), (5, '5 años')]

    nombre = models.CharField(max_length=200, unique=True, verbose_name='Nombre')
    codigo = models.CharField(max_length=20, unique=True, verbose_name='Código')
    duracion_anos = models.PositiveSmallIntegerField(
        choices=DURACION_CHOICES, default=5, verbose_name='Duración'
    )

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Carrera'
        verbose_name_plural = 'Carreras'

    def __str__(self):
        return f"{self.codigo} – {self.nombre}"


class Materia(models.Model):
    ANO_CHOICES = [(i, f'{i}° Año') for i in range(1, 6)]
    CUATRIMESTRE_CHOICES = [(1, '1° Cuatrimestre'), (2, '2° Cuatrimestre'), (3, 'Anual')]

    carrera = models.ForeignKey(
        Carrera, on_delete=models.CASCADE, related_name='materias', verbose_name='Carrera'
    )
    nombre = models.CharField(max_length=200, verbose_name='Nombre')
    codigo = models.CharField(max_length=30, blank=True, verbose_name='Código')
    ano = models.PositiveSmallIntegerField(choices=ANO_CHOICES, verbose_name='Año')
    cuatrimestre = models.PositiveSmallIntegerField(
        choices=CUATRIMESTRE_CHOICES, verbose_name='Cuatrimestre'
    )

    class Meta:
        ordering = ['ano', 'cuatrimestre', 'nombre']
        verbose_name = 'Materia'
        verbose_name_plural = 'Materias'

    def __str__(self):
        return f"{self.nombre} ({self.carrera.codigo} – {self.ano}° año, {self.cuatrimestre}° cuat.)"


class Horario(models.Model):
    """Un único horario por materia, con múltiples bloques de día/hora."""

    materia = models.OneToOneField(
        Materia, on_delete=models.CASCADE, related_name='horario', verbose_name='Materia'
    )
    docente = models.CharField(max_length=200, verbose_name='Docente')
    primer_dia_actividades = models.DateField(verbose_name='Primer día de actividades')

    class Meta:
        verbose_name = 'Horario'
        verbose_name_plural = 'Horarios'

    def __str__(self):
        return f"Horario de {self.materia.nombre}"


class HorarioBloque(models.Model):
    """Un bloque día+hora dentro de un horario."""

    DIA_CHOICES = [
        ('lunes', 'Lunes'),
        ('martes', 'Martes'),
        ('miercoles', 'Miércoles'),
        ('jueves', 'Jueves'),
        ('viernes', 'Viernes'),
        ('sabado', 'Sábado'),
    ]

    horario = models.ForeignKey(
        Horario, on_delete=models.CASCADE, related_name='bloques', verbose_name='Horario'
    )
    dia_semana = models.CharField(max_length=10, choices=DIA_CHOICES, verbose_name='Día')
    hora_inicio = models.TimeField(verbose_name='Hora inicio')
    hora_fin = models.TimeField(verbose_name='Hora fin')
    aula = models.CharField(max_length=100, blank=True, verbose_name='Aula')

    class Meta:
        ordering = ['dia_semana', 'hora_inicio']
        verbose_name = 'Bloque horario'
        verbose_name_plural = 'Bloques horarios'

    def __str__(self):
        return f"{self.get_dia_semana_display()} {self.hora_inicio:%H:%M}–{self.hora_fin:%H:%M}"


class MateriaAsignacion(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='asignaciones',
        verbose_name='Usuario',
    )
    materia = models.ForeignKey(
        Materia,
        on_delete=models.CASCADE,
        related_name='asignaciones',
        verbose_name='Materia',
    )

    class Meta:
        unique_together = [('usuario', 'materia')]
        verbose_name = 'Asignación de materia'
        verbose_name_plural = 'Asignaciones de materias'

    def __str__(self):
        return f"{self.usuario.username} → {self.materia.nombre}"
