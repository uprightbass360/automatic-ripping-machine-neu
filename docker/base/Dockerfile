###########################################################
# ARM (neu) base image — system dependencies, MakeMKV, HandBrake
# Built separately to cache the slow compile steps.
#
# Build:  docker build -t arm-base:latest docker/base/
# Use:    FROM arm-base:latest  (in the main Dockerfile)
###########################################################

FROM phusion/baseimage:jammy-1.0.4 AS base
RUN mkdir /opt/arm
WORKDIR /opt/arm

RUN \
    apt clean && \
    apt update && \
    apt upgrade -y -o Dpkg::Options::="--force-confold"

# arm user (uid/gid 1000) with video, cdrom, optical groups
RUN groupadd -g 1000 arm \
    && useradd -rm -d /home/arm -s /bin/bash -g arm -G video,cdrom -u 1000 arm \
    && groupadd -g 990 optical \
    && usermod -aG optical arm

ENV ARM_UID=1000
ENV ARM_GID=1000

RUN install_clean \
        git \
        wget \
        build-essential \
        libcurl4-openssl-dev \
        libssl-dev \
        gnupg \
        libudev-dev \
        udev \
        python3 \
        python3-dev \
        python3-pip

###########################################################
FROM base AS deps-ripper
RUN install_clean \
        abcde \
        eyed3 \
        atomicparsley \
        cdparanoia \
        eject \
        ffmpeg \
        flac \
        glyrc \
        id3 \
        id3v2 \
        lame \
        libavcodec-extra \
        lsdvd \
        vorbis-tools \
        opus-tools \
        fdkaac

RUN \
    install_clean libdvd-pkg && \
    dpkg-reconfigure libdvd-pkg

# Python dependencies
COPY requirements.txt ./requirements.txt
RUN pip3 install --upgrade pip wheel setuptools psutil pyudev
RUN pip3 install --ignore-installed --prefer-binary -r ./requirements.txt

###########################################################
FROM deps-ripper AS install-makemkv-handbrake

COPY scripts/install_mkv_hb_deps.sh /install_mkv_hb_deps.sh
RUN chmod +x /install_mkv_hb_deps.sh && /install_mkv_hb_deps.sh

COPY VERSION_HANDBRAKE /VERSION_HANDBRAKE
COPY scripts/install_handbrake.sh /install_handbrake.sh
RUN chmod +x /install_handbrake.sh && /install_handbrake.sh

COPY VERSION_MAKEMKV /VERSION_MAKEMKV
COPY scripts/install_makemkv.sh /install_makemkv.sh
RUN chmod +x /install_makemkv.sh && /install_makemkv.sh

RUN apt clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Healthcheck
COPY scripts/healthcheck.sh /healthcheck.sh
RUN chmod +x /healthcheck.sh
HEALTHCHECK --interval=5m --timeout=15s --start-period=30s CMD /healthcheck.sh

# Timezone
ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC
RUN install_clean tzdata && \
    ln -sf /usr/share/zoneinfo/$TZ /etc/localtime && \
    dpkg-reconfigure --frontend noninteractive tzdata

ARG VERSION
ARG BUILD_DATE
LABEL org.opencontainers.image.source=https://github.com/uprightbass360/automatic-ripping-machine-neu
LABEL org.opencontainers.image.description="ARM (neu) base dependencies"
LABEL org.opencontainers.image.license=MIT
LABEL org.opencontainers.image.version=$VERSION
LABEL org.opencontainers.image.created=$BUILD_DATE
