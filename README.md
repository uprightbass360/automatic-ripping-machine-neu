# Automatic Ripping Machine (ARM) - Neu

A fork of the [Automatic Ripping Machine](https://github.com/automatic-ripping-machine/automatic-ripping-machine) with bug fixes, improvements, and better integration with companion services.

## What is ARM?

Insert an optical disc (Blu-ray, DVD, CD) and ARM automatically detects, identifies, rips, and transcodes it. Headless and server-based, designed for unattended operation with one or more optical drives.

See the original project for full documentation: [automatic-ripping-machine/automatic-ripping-machine](https://github.com/automatic-ripping-machine/automatic-ripping-machine)

## Why This Fork?

The upstream ARM project is a solid foundation but has some areas that benefit from improvement:

- Bug fixes not yet merged upstream
- Better notification payloads for external service integration
- Improved compatibility with the companion transcoder and UI projects

Changes in this fork are documented in commit history. Where possible, fixes will be submitted as PRs to the upstream project.

## Features

All features from the original ARM, plus:

- Detects insertion of disc using udev
- Determines disc type (Blu-ray, DVD, CD, data)
- Video discs: retrieves metadata from OMDb/TMDb, rips with MakeMKV, queues transcoding
- Audio CDs: rips using abcde with MusicBrainz metadata
- Data discs: creates ISO backups
- Notifications via Apprise (Discord, Slack, Telegram, email, and many more)
- Multi-drive parallel ripping
- Flask web UI for job management

## Requirements

- A system capable of running Docker containers
- One or more optical drives
- Storage for your media library (local or NAS)

## Quick Start

### 1. Clone and configure

```bash
git clone --recurse-submodules https://github.com/uprightbass360/automatic-ripping-machine-neu.git
cd automatic-ripping-machine-neu
cp .env.example .env
```

Edit `.env` with your paths and settings. At minimum, set:

```bash
ARM_UID=1000
ARM_GID=1000
ARM_MUSIC_PATH=/home/arm/music
ARM_LOGS_PATH=/home/arm/logs
ARM_MEDIA_PATH=/home/arm/media
ARM_CONFIG_PATH=/etc/arm/config
```

### 2. Start the stack

```bash
# CPU-only (all three services)
docker compose up -d

# With NVIDIA GPU for transcoding
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

This pulls versioned images for all three services:

| Service | Image | Default Port |
|---------|-------|-------------|
| ARM ripper | `uprightbass360/automatic-ripping-machine` | 8080 |
| UI dashboard | `uprightbass360/arm-ui` | 8888 |
| Transcoder | `uprightbass360/arm-transcoder` | 5000 |

### 3. Verify

```bash
# ARM web interface
curl http://localhost:8080

# UI dashboard
curl http://localhost:8888

# Transcoder health
curl http://localhost:5000/health
```

Insert a disc and ARM handles the rest — rip, identify, transcode, and organize.

### Remote Transcoder

If your GPU is on a separate machine, use the split deployment:

```bash
cp .env.remote-transcoder.example .env
# Set TRANSCODER_HOST to the remote machine's IP
docker compose -f docker-compose.remote-transcoder.yml up -d
```

See the [transcoder README](https://github.com/uprightbass360/automatic-ripping-machine-transcoder) for setting up the remote side.

### Development

For local development with source code hot-reload:

```bash
git submodule update --init --recursive
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

This builds from the submodules under `components/` instead of pulling published images.

## Docker Images

Pre-built images are published to Docker Hub and GHCR on every release:

| Component | Docker Hub | Platforms |
|-----------|-----------|-----------|
| ARM | `uprightbass360/automatic-ripping-machine` | amd64, arm64, arm/v7 |
| UI | `uprightbass360/arm-ui` | amd64, arm64 |
| Transcoder | `uprightbass360/arm-transcoder` | amd64 |

The transcoder also publishes GPU-specific tags: `:X.Y.Z-nvidia`, `:X.Y.Z-amd`, `:X.Y.Z-intel`.

### Version Pinning

Pin all three versions in your `.env` for reproducible deployments:

```bash
ARM_VERSION=1.1.0
UI_VERSION=0.2.0
TRANSCODER_VERSION=0.2.0
```

Tested version combinations are tracked in [`compatibility.yaml`](compatibility.yaml).

## Related Projects

This fork is part of a suite of projects for a complete disc-to-library pipeline:

| Project | Description |
|---------|-------------|
| **automatic-ripping-machine-neu** | Fork of ARM with fixes and improvements (this project) |
| [automatic-ripping-machine-ui](https://github.com/uprightbass360/automatic-ripping-machine-ui) | Modern replacement dashboard (SvelteKit + FastAPI) |
| [automatic-ripping-machine-transcoder](https://github.com/uprightbass360/automatic-ripping-machine-transcoder) | GPU-accelerated transcoding service |

## Upstream

This project is forked from [automatic-ripping-machine/automatic-ripping-machine](https://github.com/automatic-ripping-machine/automatic-ripping-machine), originally created by Benjamin Bryan and maintained by the ARM community.

For detailed ARM configuration, see the [upstream wiki](https://github.com/automatic-ripping-machine/automatic-ripping-machine/wiki/).

## License

[MIT License](LICENSE)
