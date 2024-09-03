# Generated by Django 3.1.5 on 2021-11-05 10:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('spectools', '0028_auto_20210514_1019'),
    ]

    operations = [
        migrations.AddField(
            model_name='datatype',
            name='description_format',
            field=models.SmallIntegerField(choices=[(1, 'Plain text'), (2, 'Raw HTML')], default=1),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='datatype',
            name='description',
            field=models.TextField(blank=True),
        ),
    ]