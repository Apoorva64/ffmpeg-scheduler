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