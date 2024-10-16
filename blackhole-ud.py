import os
import shutil
import xml.etree.ElementTree as ET
import requests
import configparser
import subprocess
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from RTN import parse  # Import the RTN library

# Load configuration from config.ini
config = configparser.ConfigParser()
config.read('config.ini')

# NZB Parsing logic
def parse_nzb(nzb_path):
    tree = ET.parse(nzb_path)
    root = tree.getroot()

    files = root.findall('file')
    file_count = len(files)
    rar_found = False

    # Check filenames and count
    for file in files:
        segments = file.findall('segments/segment')
        for segment in segments:
            if 'rar' in segment.text.lower():
                rar_found = True
                break

    return file_count, rar_found

# Extract the movie or series name from the filename using RTN
def extract_name(nzb_filename):
    parsed = parse(nzb_filename)  # Use RTN to parse the name
    return parsed.parsed_title  # Return the parsed title

# Get movie/series folder from the API via config
def get_folder_from_api(name, api_key, url, api_type):
    # Use the lookup endpoint for Radarr
    if api_type == 'Radarr':
        api_path = f'/api/v3/movie/lookup?term={requests.utils.quote(name)}'
    else:
        api_path = '/api/v3/series'  # Assuming you still want to keep this for Sonarr/Lidarr

    response = requests.get(f"{url}{api_path}", headers={"X-Api-Key": api_key})

    if response.status_code != 200:
        print(f"Error: Unable to contact {api_type} API (Status Code {response.status_code})")
        return None

    items = response.json()

    # Debugging: Print the titles returned from the API
    print(f"Retrieved items from {api_type} API:")
    for item in items:
        print(f"- {item['title']}")

    # For Radarr, return the path of the first matching item
    if api_type == 'Radarr' and items:
        return items[0]['path']  # Return the path of the first item found

    return None

# Trigger a refresh in Radarr/Sonarr/Lidarr after confirming the file exists
def trigger_refresh_in_service(name, api_key, url, api_type):
    print(f"Triggering refresh for {name} in {api_type}")
    
    # Radarr/Sonarr/Lidarr API paths differ slightly
    api_path = '/api/v3/command' 

    # Determine the correct refresh type
    command_type = 'RescanMovie' if api_type == 'Radarr' else 'RescanSeries'

    # Trigger the refresh command in the service API
    data = {"name": command_type, "movieName" if api_type == 'Radarr' else "seriesName": name}
    
    response = requests.post(f"{url}{api_path}", json=data, headers={"X-Api-Key": api_key})
    
    if response.status_code == 201:
        print(f"Successfully triggered refresh for {name} in {api_type}")
    else:
        print(f"Failed to trigger refresh for {name} in {api_type}, status code: {response.status_code}, response: {response.text}")

# Function to refresh specific directory in Usenet Rclone mount
def refresh_rclone_directory(directory):
    try:
        # Get the Usenet Rclone mount directory from config
        usenet_mount_directory = config['DEFAULT']['usenet_rclone_mount_directory']
        
        # Construct the full path for the destination folder
        full_directory = os.path.join(usenet_mount_directory, directory)

        # Check if the directory exists before calling refresh
        if not os.path.exists(full_directory):
            print(f"Warning: The directory {full_directory} does not exist before Rclone refresh.")
            return  # Skip the refresh if the directory does not exist

        # Get the Rclone VFS URL from config
        rclone_vfs_url = config['Rclone']['vfs_url']
        
        # Extract the path relative to the Usenet mount directory
        relative_directory = os.path.relpath(full_directory, usenet_mount_directory)

        # Call the Rclone vfs/refresh command for the specific relative directory
        result = subprocess.run(
            ["rclone", "rc", "vfs/refresh", f"dir={relative_directory}", f"--url={rclone_vfs_url}"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        print(f"Rclone refresh triggered for {relative_directory}: {result.stdout.decode()}")
    except subprocess.CalledProcessError as e:
        print(f"Error refreshing Rclone directory: {e.stderr.decode()}")

# Process NZB file, validate and move
def process_nzb(nzb_path, service_name, nzbs_root):
    # Get API key and URL from config based on service_name (Radarr, Sonarr, etc.)
    api_key = config[service_name]['api_key']
    url = config[service_name]['url']
    api_type = 'Radarr' if 'radarr' in service_name.lower() else 'Sonarr' if 'sonarr' in service_name.lower() else 'Lidarr'
    
    file_count, rar_found = parse_nzb(nzb_path)

    if file_count > 1:
        print(f"NZB {nzb_path} contains more than one file. Skipping.")
        return False

    if rar_found:
        print(f"NZB {nzb_path} contains a .rar file. Skipping.")
        return False

    # Extract name from NZB filename using RTN
    nzb_filename = os.path.basename(nzb_path)
    name = extract_name(nzb_filename)
    print(f"Extracted name: {name}")

    # Get the correct folder using the service API
    folder = get_folder_from_api(name, api_key, url, api_type)
    
    if folder:
        # Ensure the folder exists in /mnt/nzbs/{Movie/Series}/{Name}
        destination_folder = os.path.join(nzbs_root, 'Movies' if api_type == 'Radarr' else 'TV', os.path.basename(folder))
        os.makedirs(destination_folder, exist_ok=True)

        # Move the NZB file to the folder
        shutil.move(nzb_path, os.path.join(destination_folder, nzb_filename))
        print(f"NZB moved to: {destination_folder}")

        # Trigger Rclone refresh for the Usenet mounted directory
        refresh_rclone_directory(os.path.join('Movies', os.path.basename(folder)))  # Use the correct structure

        # Confirm the file exists after refreshing
        if os.path.exists(os.path.join(destination_folder, nzb_filename)):
            print(f"File {nzb_filename} confirmed in {destination_folder}")
            
            # Trigger refresh in Radarr/Sonarr/Lidarr
            trigger_refresh_in_service(name, api_key, url, api_type)
        else:
            print(f"File {nzb_filename} not found after refreshing {destination_folder}")
    else:
        print(f"Folder not found for: {name}")
        return False

    return True

# File System Event Handler for monitoring
class NZBHandler(FileSystemEventHandler):
    def __init__(self, nzbs_root):
        self.nzbs_root = nzbs_root

    def on_created(self, event):
        if event.is_directory:
            return

        # Determine which service (Radarr/Sonarr/Lidarr) based on folder name
        folder_name = os.path.basename(os.path.dirname(event.src_path))

        if folder_name in config.sections():
            print(f"Detected new NZB file in {folder_name}: {event.src_path}")
            print("Waiting for 5 seconds...")
            time.sleep(5)  # Wait for 5 seconds before processing
            process_nzb(event.src_path, folder_name, self.nzbs_root)
        else:
            print(f"No matching service configuration for folder: {folder_name}. Skipping.")

# Monitor the NZB import folder
def start_nzb_monitor():
    import_folder = config['DEFAULT']['nzb_import_directory']
    nzbs_root_folder = config['DEFAULT']['nzbs_root_directory']

    event_handler = NZBHandler(nzbs_root_folder)
    observer = Observer()
    observer.schedule(event_handler, import_folder, recursive=True)
    observer.start()

    print(f"Monitoring {import_folder} for new NZB files...")

    try:
        while True:
            pass  # Keep the script running
    except KeyboardInterrupt:
        observer.stop()

    observer.join()

# Example usage
if __name__ == "__main__":
    start_nzb_monitor()
