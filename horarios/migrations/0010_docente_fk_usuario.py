from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('horarios', '0009_docente_en_materia'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveField(
            model_name='materia',
            name='docente',
        ),
        migrations.AddField(
            model_name='materia',
            name='docente',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='materias_como_docente',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Docente',
            ),
        ),
    ]
