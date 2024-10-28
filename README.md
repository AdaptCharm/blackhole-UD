# Blackhole-UD

Blackhole-UD is a Blackhole downloader designed for Usenet-Drive to manage compatible NZB files for Radarr, Sonarr, and Lidarr.
It will send incompatible NZB's to SABnzbd.

## Features

- Automatic import and organization of NZB files
- Integration with SABnzbd for download management
- Support for multiple instances of Radarr, Sonarr, and Lidarr (including 4K and Anime versions)
- Rclone integration

## Prerequisites

- Docker (recommended)
- Usenet-Drive
- SABnzbd
- Radarr
- Sonarr
- Lidarr (optional)

## Configuration

Edit the `config.ini` file in `/opt/blackhole-ud` to set up your specific configuration:

- Configure the NZB import and root directories
- Set the correct API keys and URLs for SABnzbd, Radarr, Sonarr, and Lidarr instances
- Set up the Rclone VFS URL

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
## Usage

### Download Client Settings
```
Name: Blackhole-UD
Enable: [x]
NZB Folder: /mnt/nzbs/Import/radarr
Watch Folder: /mnt/remote/usenet/Import/radarr/completed/
Client Priority: 1
```
Once the container is running, it will automatically monitor the specified NZB import directory and organize files based on your configuration.

I have added SABnzbd as a download client but I have created a tag on it so that nzb downloads do not go to sabnzbd straight away, instead it gets routed through the blackhole. If it is not compatible it will send it to sabnzbd with the category set by the parent folder it came from. 

Because it has been added as a download client, the arrs will monitor the download progress from there.

## Import Script (optional)

I have added an import script `import.sh` to this repo that I use to control what happens on importing. I currently use this in conjunction with realdebrid and wanted a way to use both usenet-drive and RD together.

If the file comes from `/symlinks`:
- move the file as per normal importing operations.

If the file comes from `/Import/radarr` or any other arr folder:
- create the end path directory in the rclone usenet mount
- move the file to the directory
- create a symlink to /mnt/plex

If the file comes from `/completed/radarr` or any other arr folder:
- rclone copyto the usenet drive, this will upload it directly to usenet
- create a symlink to /mnt/plex

edit this script as per needed and then activate it in radarr > settings > media management > Import Using Script [x]

## Support

For issues, feature requests, or questions, please open an issue on the GitHub repository.
