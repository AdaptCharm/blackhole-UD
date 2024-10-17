# Blackhole-UD

Blackhole-UD is a Blackhole downloader designed for Usenet-Drive to manage compatible NZB files for Radarr, Sonarr, and Lidarr.</b>
It will send incompatible NZB's to SABnzbd.

## Features

- Automatic import and organization of NZB files
- Integration with SABnzbd for download management
- Support for multiple instances of Radarr, Sonarr, and Lidarr (including 4K and Anime versions)
- Rclone integration for cloud storage management

## Prerequisites

- Docker (recommended)
- Usenet-Drive
- SABnzbd
- Radarr
- Sonarr
- Lidarr (optional)
- Rclone (installed with Dockerfile)

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/blackhole-ud.git
   cd blackhole-ud
   ```

2. Create a `config.ini` file in the `blackhole-ud` directory and configure it according to your setup. Use the provided `sampleconfig.ini` as a template.

3. Create a `docker-compose.yml` file in the project directory with the following content:
   ```yaml
   version: "3.8"

   services:
     blackhole-ud:
       restart: unless-stopped
       container_name: blackhole-ud
       build: .
       hostname: blackhole-ud
       user: 1000:1000
       environment:
         - PUID=1000
         - PGID=1000
         - TZ=Etc/UTC
       volumes:
         - /opt/blackhole-ud:/app/config # This is where your config.ini file is located
         - /etc/localtime:/etc/localtime:ro
         - /mnt:/mnt # parent path to all mount directories. make sure /nzbs directory is within here too
   ```

4. Make sure your `/mnt` directory contains the necessary subdirectories, including the `/nzbs` directory.

5. Build and start the container:
   ```
   docker-compose up -d
   ```

## Configuration

Edit the `config.ini` file in `/opt/blackhole-ud` to set up your specific configuration:

- Set the correct API keys and URLs for SABnzbd, Radarr, Sonarr, and Lidarr instances
- Configure the NZB import and root directories
- Set up the Rclone VFS URL if you're using cloud storage

## Usage

Once the container is running, it will automatically monitor the specified NZB import directory and organize files based on your configuration.

## Support

For issues, feature requests, or questions, please open an issue on the GitHub repository.
