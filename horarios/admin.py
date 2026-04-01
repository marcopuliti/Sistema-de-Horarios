from django.contrib import admin
from django.db.models import Count
from .models import Carrera, Materia, Horario, HorarioBloque, MateriaAsignacion

admin.site.site_header = "Sistema de Horarios – Administración"
admin.site.site_title = "Horarios Facultad"
admin.site.index_title = "Panel de Control"


class HorarioBloqueInline(admin.TabularInline):
    model = HorarioBloque
    extra = 1
    fields = ('dia_semana', 'hora_inicio', 'hora_fin', 'aula')


class AsignacionInline(admin.TabularInline):
    model = MateriaAsignacion
    extra = 1
    fields = ('usuario',)
    raw_id_fields = ('usuario',)


@admin.register(Carrera)
class CarreraAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo', 'duracion_anos', 'materia_count')
    search_fields = ('nombre', 'codigo')
    ordering = ('nombre',)

    @admin.display(description='Materias')
    def materia_count(self, obj):
        return obj.materias.count()


@admin.register(Materia)
class MateriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo', 'carrera', 'ano', 'cuatrimestre', 'tiene_horario')
    list_filter = ('carrera', 'ano', 'cuatrimestre')
    search_fields = ('nombre', 'codigo', 'carrera__nombre')
    ordering = ('carrera__nombre', 'ano', 'cuatrimestre', 'nombre')
    autocomplete_fields = ('carrera',)
    inlines = [AsignacionInline]

    @admin.display(description='Horario', boolean=True)
    def tiene_horario(self, obj):
        return hasattr(obj, 'horario')


@admin.register(Horario)
class HorarioAdmin(admin.ModelAdmin):
    list_display = ('materia', 'get_carrera', 'get_ano', 'docente', 'primer_dia_actividades', 'bloques_count')
    list_filter = ('materia__carrera', 'materia__ano', 'materia__cuatrimestre')
    search_fields = ('materia__nombre', 'docente', 'aula')
    date_hierarchy = 'primer_dia_actividades'
    inlines = [HorarioBloqueInline]

    @admin.display(description='Carrera', ordering='materia__carrera__nombre')
    def get_carrera(self, obj):
        return obj.materia.carrera.nombre

    @admin.display(description='Año', ordering='materia__ano')
    def get_ano(self, obj):
        return f"{obj.materia.ano}° año"

    @admin.display(description='Bloques')
    def bloques_count(self, obj):
        return obj.bloques.count()


@admin.register(MateriaAsignacion)
class MateriaAsignacionAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'materia', 'get_carrera', 'get_ano', 'get_cuatrimestre')
    list_filter = ('materia__carrera', 'materia__ano', 'materia__cuatrimestre')
    search_fields = ('usuario__username', 'usuario__first_name', 'materia__nombre')
    raw_id_fields = ('usuario',)
    autocomplete_fields = ('materia',)

    @admin.display(description='Carrera', ordering='materia__carrera__nombre')
    def get_carrera(self, obj):
        return obj.materia.carrera.nombre

    @admin.display(description='Año', ordering='materia__ano')
    def get_ano(self, obj):
        return f"{obj.materia.ano}° año"

    @admin.display(description='Cuatrimestre', ordering='materia__cuatrimestre')
    def get_cuatrimestre(self, obj):
        return f"{obj.materia.cuatrimestre}° cuat."
