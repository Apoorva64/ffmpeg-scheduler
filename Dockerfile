FROM ghcr.io/apoorva64/ffmpeg-scheduler/base:latest
# Copy the application folder inside the container
COPY . /usr/src/app

# set the default directory where CMD will executew
WORKDIR /usr/src/app

RUN python3 manage.py makemigrations
RUN python3 manage.py collectstatic --noinput

RUN chmod 777 deployment/entry_point.sh && \
    chmod 777 deployment/entry_point_celery.sh && \
    chmod 777 deployment/entry_point_celery_beat.sh