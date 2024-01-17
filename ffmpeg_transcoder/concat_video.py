import hashlib
from pathlib import Path

from celery import shared_task
from celery_progress.backend import ProgressRecorder
from django.conf import settings
from ffmpeg import FFmpeg, FFmpegError, Progress
from minio.commonconfig import Tags

from ffmpeg_transcoder.models import Folder


@shared_task(bind=True)
def concat_video(self, input_folder_id, output_folder_id, r_filename: str):
    print("Concat video")
    input_folder = Folder.objects.get(pk=input_folder_id)
    output_folder = Folder.objects.get(pk=output_folder_id)
    input_folder_client = input_folder.bucket.connection.get_client()
    output_folder_client = output_folder.bucket.connection.get_client()
    progress_recorder = ProgressRecorder(self)
    progress_recorder.set_progress(0, 100, description="Concat video for file: " + r_filename)
    # Download files in a folder
    hashed_folder = hashlib.md5((r_filename + str(input_folder.id) + "concatVideo").encode()).hexdigest()
    folder_download_path = settings.DOWNLOAD_FOLDER / hashed_folder

    folder_download_path.mkdir(parents=True, exist_ok=True)
    for object in input_folder_client.list_objects(input_folder.bucket.name, input_folder.prefix):
        object_download_path = folder_download_path / object.object_name
        print("Downloading file", object.object_name + " to ", object_download_path)
        if not object_download_path.exists():
            input_folder_client.fget_object(input_folder.bucket.name,
                                            input_folder.prefix + "/" + object.object_name, object_download_path)

    hashed_output_file = settings.UPLOAD_FOLDER / (hashed_folder + Path(r_filename).suffix)

    # Concat files
    ffmpeg = (
        FFmpeg()
        .option('y')
        .input(str(folder_download_path / "*.mkv"))
        .output(str(hashed_output_file), {
            'c': 'copy',
            'map': '0',
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
        hashed_output_file.unlink()
        # Set scheduled tag
        tags = Tags()
        tags["scheduled"] = "false"
        input_folder_client.set_object_tags(
            input_folder.bucket.name,
            input_folder.prefix + "/" + r_filename,
            tags,
        )
        raise e

    # Upload file
    output_folder_client.fput_object(
        output_folder.bucket.name,
        output_folder.prefix + "/" + r_filename,
        hashed_output_file.as_posix(),
    )

    folder_download_path.rmdir()
    # delete file
    hashed_output_file.unlink()
    # Delete input file
    input_folder_client.remove_object(
        input_folder.bucket.name,
        input_folder.prefix + "/" + r_filename
    )
    progress_recorder.set_progress(100, 100, description="Splitting completed")

    return f"Splitting completed for file: {r_filename} 🎉"
