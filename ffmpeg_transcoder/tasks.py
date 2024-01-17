import re
import subprocess
from pathlib import Path

import celery
from celery import shared_task
from celery_progress.backend import ProgressRecorder
from ffmpeg import FFmpeg, Progress, FFmpegError
from minio.commonconfig import Tags
from django.conf import settings

from ffmpeg_scheduler.celery import app
from ffmpeg_transcoder.models import Folder
import hashlib
from ffmpeg_transcoder.split_video import split_video


@shared_task()
def update_task(input_folder_id, output_folder_id):
    input_folder = Folder.objects.get(pk=input_folder_id)
    input_folder_client = input_folder.bucket.connection.get_client()
    output_folder = Folder.objects.get(pk=output_folder_id)
    split_folder = Folder.objects.get_or_create(prefix=output_folder.prefix + "/split", bucket=output_folder.bucket)[0]
    transcoded_parts_folder = Folder.objects.get_or_create(prefix=output_folder.prefix + "/transcode-parts",
                                                           bucket=output_folder.bucket)[0]
    # list files in bucket in path /video_to_transcode
    for obj in input_folder_client.list_objects(input_folder.bucket.name, prefix=input_folder.prefix, recursive=True):
        tags = input_folder_client.get_object_tags(input_folder.bucket.name, obj.object_name)
        if tags is None or tags.get("scheduled") is None or tags.get("scheduled") == "false":
            print("Scheduling file: ", obj.object_name)
            # Create Folder to contain split files

            split_video.delay(input_folder_id, split_folder.id,
                              obj.object_name.removeprefix(input_folder.prefix + "/"))
            # Set scheduled tag
            tags = Tags()
            tags["scheduled"] = "true"
            input_folder_client.set_object_tags(
                input_folder.bucket.name,
                obj.object_name,
                tags,
            )
    for obj in split_folder.bucket.connection.get_client().list_objects(split_folder.bucket.name,
                                                                        prefix=split_folder.prefix,
                                                                        recursive=True):
        tags = split_folder.bucket.connection.get_client().get_object_tags(split_folder.bucket.name, obj.object_name)
        if tags is not None and (tags.get("scheduled") is None or tags.get("scheduled") == "false"):
            path = Path(obj.object_name)
            from_folder = Folder.objects.get_or_create(prefix=path.parent.as_posix(),
                                                       bucket=split_folder.bucket)[0]
            processed_folder = Folder.objects.get_or_create(prefix=transcoded_parts_folder.prefix + "/" + path.parent.name,
                                                            bucket=output_folder.bucket)[0]
            # Create Folder to contain split files
            transcode_job.delay(from_folder.id, processed_folder.id, path.name)
            # Set scheduled tag
            tags = split_folder.bucket.connection.get_client().get_object_tags(split_folder.bucket.name,
                                                                               obj.object_name)
            tags["scheduled"] = "true"
            split_folder.bucket.connection.get_client().set_object_tags(
                split_folder.bucket.name,
                obj.object_name,
                tags,
            )



def get_frame_count(file_path):
    ffprobe_cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_packets', '-show_entries',
                   'stream=nb_read_packets', '-of', 'csv=p=0', str(file_path)]

    ffprobe_output = subprocess.check_output(ffprobe_cmd, universal_newlines=True)

    # parse string and extract int with re
    return int(re.search(r'\d+', ffprobe_output).group())


@shared_task(bind=True)
def transcode_job(self, input_folder_id, output_folder_id, r_filename: str):
    input_folder = Folder.objects.get(pk=input_folder_id)
    output_folder = Folder.objects.get(pk=output_folder_id)
    input_folder_client = input_folder.bucket.connection.get_client()
    output_folder_client = output_folder.bucket.connection.get_client()
    progress_recorder = ProgressRecorder(self)
    progress_recorder.set_progress(0, 100, description="Transcoding job started for file: " + r_filename)
    print("Transcoding job started for file: ", r_filename, " from folder: ", input_folder.prefix, " to folder: ",
          output_folder.prefix, " with input bucket: ", input_folder.bucket.name, " and output bucket: ",
          output_folder.bucket.name)
    # Download file
    hashed_filename = hashlib.md5((r_filename + str(input_folder.id)).encode()).hexdigest() + Path(r_filename).suffix

    object_download_path = Path(settings.DOWNLOAD_FOLDER) / hashed_filename
    object_download_path.parent.mkdir(parents=True, exist_ok=True)

    object_upload_path = (Path(settings.UPLOAD_FOLDER) / hashed_filename).with_suffix(".mkv")
    object_upload_path.parent.mkdir(parents=True, exist_ok=True)

    progress_recorder.set_progress(0, 100, description="Downloading file: " + r_filename)

    # Download minio file from bucket
    input_folder_client.fget_object(
        input_folder.bucket.name,
        input_folder.prefix + "/" + r_filename,
        object_download_path
    )

    # Get progress total number of frames
    total_frames = get_frame_count(object_download_path)

    # Convert file
    ffmpeg = (
        FFmpeg()
        .option('y')
        .input(object_download_path)
        .output(
            object_upload_path,
            {
                'c:v': 'libx264',
                'c:a': 'aac',
                'c:s': 'copy',
                'ac': '2',
                'pix_fmt': 'yuv420p',
                'map': '0'
            }
        )
    )
    task_id = self.request.id

    @ffmpeg.on("progress")
    def on_progress(progress: Progress):
        print(
            f"Task ID: {task_id} - Frame: {progress.frame} - Total Frames: {total_frames} - Fps: {progress.fps}")

    @ffmpeg.on("completed")
    def on_completed():
        print("Job Completed !!! 🎉")

    try:
        print("Starting transcoding")
        ffmpeg.execute()

    except FFmpegError as e:
        if object_upload_path.is_file():
            object_upload_path.unlink()
        # Set scheduled tag
        tags = Tags()
        tags["scheduled"] = "false"
        input_folder_client.set_object_tags(
            input_folder.bucket.name,
            input_folder.prefix + "/" + r_filename,
            tags,
        )
        raise e
    print("Transcoding completed")
    progress_recorder.set_progress(total_frames, total_frames, description="Transcoding completed")
    progress_recorder.set_progress(0, 100, description="Uploading transcoded file")
    print("Uploading transcoded file")
    # Upload file
    output_folder_client.fput_object(
        output_folder.bucket.name,
        Path(output_folder.prefix + "/" + r_filename).with_suffix(".mkv").as_posix(),
        object_upload_path
    )
    # copy tags
    tags = input_folder_client.get_object_tags(input_folder.bucket.name, input_folder.prefix + "/" + r_filename)
    tags["scheduled"] = "false"
    tags["finished"] = "true"
    output_folder_client.set_object_tags(
        output_folder.bucket.name,
        Path(output_folder.prefix + "/" + r_filename).with_suffix(".mkv").as_posix(),
        tags,
    )



    progress_recorder.set_progress(100, 100, description="Upload completed")
    progress_recorder.set_progress(0, 100, description="Deleting input file")
    print("Deleting input file")
    # Delete input file
    input_folder_client.remove_object(
        input_folder.bucket.name,
        input_folder.prefix + "/" + r_filename
    )
    progress_recorder.set_progress(100, 100, description="Input file deleted")
    progress_recorder.set_progress(0, 100, description="Deleting local files")
    print("Deleting local files")
    # Delete local files
    object_download_path.unlink()
    object_upload_path.unlink()
    progress_recorder.set_progress(100, 100, description="Local files deleted")
    print("Job completed")
    return {
        "filename": r_filename
    }
