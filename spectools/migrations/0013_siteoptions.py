# Generated by Django 3.1.5 on 2021-03-29 14:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('spectools', '0012_xmlelement_is_root'),
    ]

    operations = [
        migrations.CreateModel(
            name='SiteOptions',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('site_name', models.CharField(max_length=100)),
                ('xml_format_name', models.CharField(max_length=100)),
            ],
            options={
                'verbose_name_plural': 'site options',
                'db_table': 'site_options',
            },
        ),
    ]
