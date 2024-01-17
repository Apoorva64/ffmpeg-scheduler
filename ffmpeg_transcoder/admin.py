from django.contrib import admin
from django.forms import ModelChoiceField

from ffmpeg_transcoder.split_video import split_video
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


@admin.action(description='Run split video')
def split_video_action(self, request, queryset):
    for folder in queryset:
        split_video.delay(folder.id, int(request.POST['output_folder']), "The Office (US) - S05E26 - Company Picnic.mkv")



@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = ['prefix', 'bucket']
    action_form = FolderUpdateActionForm

    actions = [run_transcoding, split_video_action]


