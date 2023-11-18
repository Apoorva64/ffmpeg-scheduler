FROM python:3.11-bookworm
ENV TZ=Europe/Paris
# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN apt-get update && apt-get install ffmpeg gunicorn3 -y

# install python packages
COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

# Copy the application folder inside the container
COPY . /usr/src/app

# set the default directory where CMD will executew
WORKDIR /usr/src/app

RUN python3 manage.py makemigrations
RUN python3 manage.py collectstatic --noinput

RUN chmod 777 deployment/entry_point.sh && \
    chmod 777 deployment/entry_point_celery.sh && \
    chmod 777 deployment/entry_point_celery_beat.sh