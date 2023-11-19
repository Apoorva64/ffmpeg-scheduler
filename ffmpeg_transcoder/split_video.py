import hashlib
from pathlib import Path

from celery import shared_task
from celery_progress.backend import ProgressRecorder
from minio.commonconfig import Tags

from ffmpeg_transcoder.models import Folder
from ffmpeg import FFmpeg, Progress, FFmpegError
from django.conf import settings


@shared_task(bind=True)
def split_video(self, input_folder_id, output_folder_id, r_filename: str):
    input_folder = Folder.objects.get(pk=input_folder_id)
    output_folder = Folder.objects.get(pk=output_folder_id)
    input_folder_client = input_folder.bucket.connection.get_client()
    output_folder_client = output_folder.bucket.connection.get_client()
    progress_recorder = ProgressRecorder(self)
    progress_recorder.set_progress(0, 100, description="Splitting video for file: " + r_filename)
    # Download file
    hashed_filename = hashlib.md5((r_filename + str(input_folder.id) + "splitVideo").encode()).hexdigest() + Path(
        r_filename).suffix
    object_download_path = settings.DOWNLOAD_FOLDER / hashed_filename
    input_folder_client.fget_object(input_folder.bucket.name,
                                    input_folder.prefix + "/" + r_filename, object_download_path)

    # Create output folder
    output_folder_path = Path(settings.UPLOAD_FOLDER) / hashed_filename
    output_folder_path.parent.mkdir(parents=True, exist_ok=True)

    template = str((output_folder_path / "%03d").with_suffix(Path(r_filename).suffix))
    # Split video
    ffmpeg = (
        FFmpeg()
        .option('y')
        .input(str(object_download_path))
        .output(template, {
            'c': 'copy',
            'map': '0',
            'segment_time': '00:10:00',
            'f': 'segment',
            'reset_timestamps': '1'
        })
    )

    task_id = self.request.id

    @ffmpeg.on("progress")
    def on_progress(progress: Progress):
        print(
            f"Task ID: {task_id} - Frame: {progress.frame}  - Fps: {progress.fps}")

    @ffmpeg.on("completed")
    def on_completed():
        print("Job Completed !!! 🎉")

    try:
        print("Starting transcoding")
        ffmpeg.execute()

    except FFmpegError as e:
        output_folder_path.unlink()
        # Set scheduled tag
        tags = Tags()
        tags["scheduled"] = "false"
        input_folder_client.set_object_tags(
            input_folder.bucket.name,
            input_folder.prefix + "/" + r_filename,
            tags,
        )
        raise e

    # Upload folder
    for file in output_folder_path.glob("*"):
        output_folder_client.fput_object(output_folder.bucket.name, output_folder.prefix + "/" + file.name, file)
        # tag file
        tags = Tags()
        tags["scheduled"] = "false"
        tags["parent"] = r_filename
        tags["type"] = "split"
        output_folder_client.set_object_tags(
            output_folder.bucket.name,
            output_folder.prefix + "/" + file.name,
            tags,
        )
        file.unlink()

    output_folder_path.rmdir()
    # delete file
    object_download_path.unlink()

    # Set scheduled tag
    tags = Tags()
    tags["scheduled"] = "false"
    input_folder_client.set_object_tags(
        input_folder.bucket.name,
        input_folder.prefix + "/" + r_filename,
        tags,
    )
    print("Splitting completed")
    progress_recorder.set_progress(100, 100, description="Splitting completed")

    return f"Splitting completed for file: {r_filename} 🎉"
