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

## Docker Images

Pre-built multi-platform images (`amd64`, `arm64`, `arm/v7`) are available from Docker Hub and GHCR:

```bash
# Docker Hub
docker pull uprightbass360/automatic-ripping-machine:latest
docker pull uprightbass360/automatic-ripping-machine:2.21.5

# GHCR
docker pull ghcr.io/uprightbass360/automatic-ripping-machine-neu:latest
docker pull ghcr.io/uprightbass360/automatic-ripping-machine-neu:2.21.5
```

## Install

Docker is the recommended deployment method:

```bash
git clone https://github.com/uprightbass360/automatic-ripping-machine-neu.git
cd automatic-ripping-machine-neu
```

For detailed installation instructions, see the [upstream wiki](https://github.com/automatic-ripping-machine/automatic-ripping-machine/wiki/).

## Related Projects

This fork is part of a suite of projects for a complete disc-to-library pipeline:

| Project | Description |
|---------|-------------|
| **automatic-ripping-machine-neu** | Fork of ARM with fixes and improvements (this project) |
| [automatic-ripping-machine-ui](https://github.com/uprightbass360/automatic-ripping-machine-ui) | Modern replacement dashboard (SvelteKit + FastAPI) |
| [automatic-ripping-machine-transcoder](https://github.com/uprightbass360/automatic-ripping-machine-transcoder) | GPU-accelerated transcoding service |

## Upstream

This project is forked from [automatic-ripping-machine/automatic-ripping-machine](https://github.com/automatic-ripping-machine/automatic-ripping-machine), originally created by Benjamin Bryan and maintained by the ARM community.

## License

[MIT License](LICENSE)
