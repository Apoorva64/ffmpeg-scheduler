# Generated by Django 4.2.7 on 2023-11-18 10:08

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Bucket',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='MinioConnection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('endpoint', models.CharField(max_length=255)),
                ('access_key', models.CharField(max_length=255)),
                ('secret_key', models.CharField(max_length=255)),
                ('secure', models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name='Folder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('prefix', models.CharField(max_length=255)),
                ('bucket', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ffmpeg_transcoder.bucket')),
            ],
        ),
        migrations.AddField(
            model_name='bucket',
            name='connection',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ffmpeg_transcoder.minioconnection'),
        ),
    ]
