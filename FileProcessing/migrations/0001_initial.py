# Generated by Django 5.0.6 on 2024-05-20 05:01

import FileProcessing.utils
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='File',
            fields=[
                ('fileID', models.CharField(max_length=255, primary_key=True, serialize=False, unique=True)),
                ('file', models.FileField(blank=True, null=True, upload_to=FileProcessing.utils.file_generate_upload_path)),
                ('original_file_name', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('file_name', models.CharField(max_length=255, unique=True)),
                ('file_type', models.CharField(max_length=255)),
                ('file_size', models.IntegerField()),
                ('upload_finished_at', models.DateTimeField(blank=True, null=True)),
                ('is_delete_init', models.BooleanField(default=False)),
                ('delete_init_at', models.DateTimeField(blank=True, null=True)),
                ('uploaded_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='UserPersonalFileToken',
            fields=[
                ('personalfiletoken', models.CharField(max_length=200, primary_key=True, serialize=False, unique=True)),
                ('is_delete_init', models.BooleanField(default=False)),
                ('is_deleted', models.BooleanField(default=False)),
                ('is_copied', models.BooleanField(default=False)),
                ('file_size', models.IntegerField()),
                ('type', models.CharField(max_length=255)),
                ('parent', models.CharField(default='*', max_length=255)),
                ('modified_at', models.DateTimeField(auto_now_add=True)),
                ('delete_init_at', models.DateTimeField(blank=True, null=True)),
                ('favourite', models.BooleanField(default=False)),
                ('change_file_name', models.TextField(blank=True, null=True)),
                ('views', models.IntegerField(default=0)),
                ('file_id', models.ForeignKey(on_delete=django.db.models.deletion.RESTRICT, to='FileProcessing.file')),
                ('uploaded_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]