# Generated by Django 3.1.5 on 2021-03-30 13:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('spectools', '0018_staticpage_staticpagecollection'),
    ]

    operations = [
        migrations.AddField(
            model_name='datatype',
            name='regex',
            field=models.CharField(blank=True, max_length=200),
        ),
    ]
