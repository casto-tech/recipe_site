import django.contrib.postgres.indexes
import django.contrib.postgres.search
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('slug', models.SlugField(unique=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Recipe',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('slug', models.SlugField(unique=True)),
                ('image', models.ImageField(blank=True, null=True, upload_to='recipes/')),
                ('image_url', models.URLField(blank=True, help_text='Developer-controlled fallback URL — never rendered from user input.')),
                ('ingredients', models.TextField(help_text='Enter one ingredient per line. Example: 2 cups flour')),
                ('directions', models.TextField(help_text='Enter one step per line. These will be displayed as a numbered list.')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('search_vector', django.contrib.postgres.search.SearchVectorField(blank=True, null=True)),
                ('tags', models.ManyToManyField(blank=True, to='recipes.tag')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='recipe',
            index=django.contrib.postgres.indexes.GinIndex(fields=['search_vector'], name='recipes_rec_search__idx'),
        ),
    ]
