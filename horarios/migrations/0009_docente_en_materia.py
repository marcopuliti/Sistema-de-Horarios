from django.db import migrations, models


def copiar_docente_a_materia(apps, schema_editor):
    Horario = apps.get_model('horarios', 'Horario')
    for h in Horario.objects.select_related('materia').iterator():
        if h.docente:
            h.materia.docente = h.docente
            h.materia.save(update_fields=['docente'])


class Migration(migrations.Migration):

    dependencies = [
        ('horarios', '0008_aula_modelo'),
    ]

    operations = [
        # 1. Agregar docente a Materia
        migrations.AddField(
            model_name='materia',
            name='docente',
            field=models.CharField(blank=True, default='', max_length=200, verbose_name='Docente'),
            preserve_default=False,
        ),
        # 2. Copiar datos de Horario.docente → Materia.docente
        migrations.RunPython(copiar_docente_a_materia, migrations.RunPython.noop),
        # 3. Quitar docente de Horario
        migrations.RemoveField(
            model_name='horario',
            name='docente',
        ),
    ]
