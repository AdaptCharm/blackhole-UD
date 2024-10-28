#!/bin/bash
set -e

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

for cmd in mv rclone rm ln cut rev echo; do
    if ! command_exists "$cmd"; then
        echo "Error: Required command '$cmd' not found." >&2
        exit 1
    fi
done

currentpath="$1"
endpath="$2"
usenetmount="/mnt/remote/usenet"

echo "Debug: currentpath = $currentpath" >&2
echo "Debug: endpath = $endpath" >&2
echo "Debug: usenetmount = $usenetmount" >&2

getcutpathradarr () { while read data; do echo "$data" | rev | cut -d'/' -f 1-3 | rev; done; }
getcutpathsonarr () { while read data; do echo "$data" | rev | cut -d'/' -f 1-4 | rev; done; }

if [[ $currentpath = *'symlinks'* ]]; then
    echo "Debug: Moving symlink" >&2
    mv "$currentpath" "$endpath"
elif [[ $currentpath = *'Import/radarr'* ]]; then
    echo "Debug: Processing Import/radarr path" >&2
    rclone_dest=$(echo $endpath | getcutpathradarr)
    dest_dir="$usenetmount/$rclone_dest"
    dest_dir_parent=$(dirname "$dest_dir")
    echo "Debug: Creating directory: $dest_dir_parent" >&2
    mkdir -p "$dest_dir_parent"
    echo "Debug: moving $currentpath to destination: $dest_dir" >&2
    mv "$currentpath" "$dest_dir"
    ln -s -d -f "$dest_dir" "$endpath"
    echo "moved and linked $currentpath to $dest_dir" >> /scripts/arrs/move.log
elif [[ $currentpath = *'Import/sonarr'* ]]; then
    echo "Debug: Processing Import/sonarr path" >&2
    rclone_dest=$(echo $endpath | getcutpathsonarr)
    dest_dir="$usenetmount/$rclone_dest"
    dest_dir_parent=$(dirname "$dest_dir")
    echo "Debug: Creating directory: $dest_dir_parent" >&2
    mkdir -p "$dest_dir_parent"
    echo "Debug: moving $currentpath to destination: $dest_dir" >&2
    mv "$currentpath" "$dest_dir"
    ln -s -d -f "$dest_dir" "$endpath"
    echo "moved and linked $currentpath to $dest_dir" >> /scripts/arrs/move.log
    echo "moved $currentpath to $endpath" >> /scripts/arrs/move.log
elif [[ $currentpath = *'complete/radarr'* ]]; then
    echo "Debug: Processing Radarr path" >&2
    rclone_dest=$(echo $endpath | getcutpathradarr)
    echo "Debug: rclone destination: $rclone_dest" >&2
    rclone copyto "$currentpath" "usenet:/$rclone_dest" \
        --log-file /scripts/arrs/rclone.log --config /config/rclone/rclone.conf
    rm -rf "$currentpath"
    ln -s -d -f "$usenetmount/$rclone_dest" "$endpath"
    echo "linked $usenetmount/$rclone_dest to $endpath" >> /scripts/arrs/rclone.log
elif [[ $currentpath = *'complete/sonarr'* ]]; then
    echo "Debug: Processing Sonarr path" >&2
    rclone_dest=$(echo $endpath | getcutpathsonarr)
    echo "Debug: rclone destination: $rclone_dest" >&2
    rclone copyto "$currentpath" "usenet:/$rclone_dest" \
        --log-file /scripts/arrs/rclone.log --config /config/rclone/rclone.conf
    rm -rf "$currentpath"
    ln -s -d -f "$usenetmount/$rclone_dest" "$endpath"
    echo "linked $usenetmount/$rclone_dest to $endpath" >> /scripts/arrs/rclone.log
else
    echo "Error: Unrecognized path pattern in currentpath: $currentpath" >&2
    exit 1
fi

echo "Debug: Script completed successfully" >&2
