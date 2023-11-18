from django.db import models
from minio import Minio


# Create your models here.
class MinioConnection(models.Model):
    endpoint = models.CharField(max_length=255)
    access_key = models.CharField(max_length=255)
    secret_key = models.CharField(max_length=255)
    secure = models.BooleanField(default=True)

    def __str__(self):
        return self.endpoint

    def get_client(self):
        return Minio(
            endpoint=self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure,
        )


class Bucket(models.Model):
    name = models.CharField(max_length=255)
    connection = models.ForeignKey(MinioConnection, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class Folder(models.Model):
    prefix = models.CharField(max_length=255)
    bucket = models.ForeignKey(Bucket, on_delete=models.CASCADE)

    def __str__(self):
        return self.prefix + " - " + self.bucket.name
