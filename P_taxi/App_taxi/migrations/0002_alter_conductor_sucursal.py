import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('App_taxi', '0001_initial'),
    ]

    operations = [
        # La columna ya se crea null=True en 0001. Este bloque no emite SQL
        # (evita el ALTER TABLE que se cuelga en MariaDB/XAMPP por metadata locks)
        # y solo sincroniza el estado interno del ORM de Django.
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name='conductor',
                    name='sucursal',
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='conductores',
                        to='App_taxi.sucursal',
                    ),
                ),
            ],
        ),
    ]
