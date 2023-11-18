from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Creates the initial admin user with the provided username and password or from environment variables"

    def handle(self, *args, **options):
        # get username and password from environment variables
        username = settings.DJANGO_ADMIN_USERNAME
        password = settings.DJANGO_ADMIN_PASSWORD

        # create admin user
        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f'Admin user with username {username} already exists'))
        else:
            User.objects.create_superuser(username=username, password=password)
            self.stdout.write(self.style.SUCCESS(f'Successfully created admin user with username {username}'))
