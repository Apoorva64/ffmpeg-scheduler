from django.contrib import admin
from django.forms import ModelChoiceField

# Register your models here.
from ffmpeg_transcoder.models import MinioConnection, Bucket, Folder
from ffmpeg_transcoder.tasks import update_task
from django.contrib.admin.helpers import ActionForm


class FolderUpdateActionForm(ActionForm):
    output_folder = ModelChoiceField(queryset=Folder.objects.all())


@admin.register(MinioConnection)
class MinioConnectionAdmin(admin.ModelAdmin):
    list_display = ['endpoint', 'access_key', 'secure']


@admin.register(Bucket)
class BucketAdmin(admin.ModelAdmin):
    list_display = ['name', 'connection']


# update action

@admin.action(description='Run transcoding')
def run_transcoding(self, request, queryset):
    for folder in queryset:
        update_task.delay(folder.id, int(request.POST['output_folder']))


@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = ['prefix', 'bucket']
    action_form = FolderUpdateActionForm

    actions = [run_transcoding]


