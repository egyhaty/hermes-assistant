FROM python:3.13-slim-bookworm@sha256:e32be0e55814a08977501ca863271d9bd02443710db8f2afaf8372e2c4508530
ARG UPSTREAM_REV=e0b2401a7a7b333eab0b518e80be5285c3ee85c5
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DISPLAY=:99 HOME=/data PYTHONPATH=/opt/jobapp:/opt/worker XDG_RUNTIME_DIR=/tmp/runtime
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends chromium chromium-driver xvfb x11vnc novnc websockify xauth fonts-dejavu-core python3-tk curl ca-certificates procps && rm -rf /var/lib/apt/lists/*
RUN mkdir /opt/jobapp && curl -fsSL "https://codeload.github.com/GodsScion/Auto_job_applier_linkedIn/tar.gz/${UPSTREAM_REV}" | tar xz --strip-components=1 -C /opt/jobapp
RUN pip install --no-cache-dir -r /opt/jobapp/requirements.txt gunicorn aiohttp && pip freeze > /opt/python-lock.txt
COPY job-worker/ /opt/worker/
RUN python /opt/worker/patch_upstream.py && python -m compileall -q /opt/jobapp /opt/worker && useradd -u 10000 -m worker && mkdir /data && chown 10000:10000 /data
WORKDIR /data
USER 10000:10000
ENTRYPOINT ["python", "/opt/worker/serve.py"]
