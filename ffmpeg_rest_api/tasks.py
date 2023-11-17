import re
import subprocess
from pathlib import Path

from celery import shared_task
from celery_progress.backend import ProgressRecorder
from ffmpeg import FFmpeg, Progress, FFmpegError
from minio import Minio
from minio.error import S3Error
from minio.commonconfig import Tags
from django.conf import settings

client = Minio(
    endpoint=settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=settings.MINIO_SECURE,
)

BUCKET_NAME = "h264-transcoding"


@shared_task()
def update():
    # list files in bucket in path /video_to_transcode
    for obj in client.list_objects(BUCKET_NAME, prefix="input", recursive=True):
        transcode_job.delay(obj.object_name)


def get_frame_count(file_path):
    ffprobe_cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_packets', '-show_entries',
                   'stream=nb_read_packets', '-of', 'csv=p=0', str(file_path)]

    ffprobe_output = subprocess.check_output(ffprobe_cmd, universal_newlines=True)

    # parse string and extract int with re
    return int(re.search(r'\d+', ffprobe_output).group())


INPUT_FOLDER = "input"
OUTPUT_FOLDER = "output"


@shared_task(bind=True)
def transcode_job(self, filename: str):
    progress_recorder = ProgressRecorder(self)
    progress_recorder.set_progress(0, 100, description="Transcoding job started for file: " + filename)

    input_file_path = Path(filename).name
    output_file_path = Path(input_file_path).with_stem(Path(input_file_path).stem + "_converted").with_suffix('.mkv')

    # Download minio file from bucket
    client.fget_object(
        BUCKET_NAME,
        filename,
        input_file_path,
    )

    # Get progress total number of frames
    total_frames = get_frame_count(input_file_path)

    # Convert file
    ffmpeg = (
        FFmpeg()
        .option('y')
        .input(input_file_path)
        .output(
            output_file_path,
            {
                'c:v': 'libx264',
                'c:a': 'aac',
                'c:s': 'srt',
                'ac': '2',
                'pix_fmt': 'yuv420p',
                'map': '0'
            }
        )
    )

    @ffmpeg.on("progress")
    def on_progress(progress: Progress):
        print(f"Processing frame {progress.frame} of {total_frames}")
        # progress_recorder.set_progress(progress.frame, total_frames)

    @ffmpeg.on("completed")
    def on_completed():
        print("Job Completed !!! 🎉")

    try:
        print("Starting transcoding")
        ffmpeg.execute()

    except FFmpegError as e:
        if output_file_path.is_file():
            output_file_path.unlink()
        return {
            "error": e,
            "filename": filename
        }
    print("Transcoding completed")
    progress_recorder.set_progress(total_frames, total_frames)
    print("Uploading transcoded file")
    # Upload file
    client.fput_object(
        BUCKET_NAME,
        filename.replace(INPUT_FOLDER, OUTPUT_FOLDER),
        output_file_path
    )

    print("Transcoding job completed for file: " + filename)
    # Delete input file
    client.remove_object(BUCKET_NAME, filename)

    if output_file_path.is_file():
        output_file_path.unlink()
    if Path(input_file_path).is_file():
        Path(input_file_path).unlink()
