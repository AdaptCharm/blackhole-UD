import os
import configparser
import xml.etree.ElementTree as ET
import requests
import logging
import time
import shutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

def setup_logging(config):
    log_level = logging.DEBUG if config.getboolean('Logging', 'debug', fallback=False) else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')

# Read configuration
config = configparser.ConfigParser()
try:
    config.read('config.ini')
    nzb_import_directory = config.get('DEFAULT', 'nzb_import_directory')
    nzbs_root_directory = config.get('DEFAULT', 'nzbs_root_directory')
    usenet_rclone_mount_directory = config.get('DEFAULT', 'usenet_rclone_mount_directory')
    RCLONE_VFS_URL = config['Rclone']['vfs_url']
    SABNZBD_URL = config['SABnzbd']['url']
    SABNZBD_API_KEY = config['SABnzbd']['api_key']
except Exception as e:
    logging.error(f"Error reading configuration: {e}")
    exit(1)

# List of streamable file extensions
STREAMABLE_EXTENSIONS = [
    '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.mpeg-ts', '.m2ts', '.webm', 
    '.iso', '.vob', '.wav', '.flac', '.ogg', '.aac', '.mp3', '.wma', '.alac', 
    '.cbr', '.cbz', '.epub', '.m4b', '.aw3'
]

# NZB Parsing logic
def parse_nzb(nzb_path):
    """Parses the NZB file to check for streamable files and the presence of .rar files."""
    try:
        logging.debug(f"Parsing NZB file: {nzb_path}")

        tree = ET.parse(nzb_path)
        root = tree.getroot()

        # Finding all 'file' elements while ignoring namespace
        files = root.findall('.//{http://www.newzbin.com/DTD/2003/nzb}file')
        streamable_found = False
        rar_found = False

        logging.debug(f"Found {len(files)} file elements in the NZB")

        # Check each file for segments
        for file in files:
            subject = file.get('subject', '')
            logging.debug(f"Processing file: {subject}")

            segments = file.findall('.//{http://www.newzbin.com/DTD/2003/nzb}segments/{http://www.newzbin.com/DTD/2003/nzb}segment')
            logging.debug(f"Found {len(segments)} segments for file: {subject}")

            # Check if any segment contains a streamable file extension
            for segment in segments:
                if segment.text:
                    # Check for streamable extensions
                    if any(ext in segment.text.lower() for ext in STREAMABLE_EXTENSIONS):
                        streamable_found = True
                        logging.debug(f"Streamable file found: {segment.text}")
                    # Check for .rar files
                    if '.rar' in segment.text.lower():
                        rar_found = True
                        logging.debug(f"RAR file found: {segment.text}")

            # Also check the subject for streamable extensions and .rar files
            if any(ext in subject.lower() for ext in STREAMABLE_EXTENSIONS):
                streamable_found = True
                logging.debug(f"Streamable file found in subject: {subject}")
            if '.rar' in subject.lower():
                rar_found = True
                logging.debug(f"RAR file found in subject: {subject}")

        logging.debug(f"Streamable files found: {streamable_found}, RAR found: {rar_found}")
        return streamable_found, rar_found

    except Exception as e:
        logging.error(f"Error parsing NZB file: {e}")
        return False, False

def is_compatible_nzb(nzb_file):
    """Determines if an NZB file is compatible based on the presence of streamable files and absence of .rar files."""
    streamable_found, rar_found = parse_nzb(nzb_file)

    # Check if there is at least one streamable file and no .rar files
    if streamable_found and not rar_found:
        logging.debug("NZB marked as compatible: Contains streamable files and no RAR segments.")
        return True
    else:
        logging.debug(f"NZB marked as incompatible: Streamable found: {streamable_found}, RAR found: {rar_found}")
        return False

def ensure_directory_exists(directory):
    """Ensure the specified directory exists, creating it if necessary."""
    try:
        os.makedirs(directory, exist_ok=True)
        logging.debug(f"Ensured directory exists: {directory}")
    except Exception as e:
        logging.error(f"Failed to create directory {directory}: {e}")
        raise

def create_arr_subdirectories(config):
    """Create subdirectories for each 'arr' service and their 'completed' folders."""
    import_dir = config.get('DEFAULT', 'nzb_import_directory')
    arr_sections = [section for section in config.sections() if 'arr' in section.lower()]
    
    created_count = 0
    for section in arr_sections:
        arr_dir = os.path.join(import_dir, section.lower())
        completed_dir = os.path.join(arr_dir, 'completed')
        if not os.path.exists(arr_dir):
            ensure_directory_exists(arr_dir)
            created_count += 1
        if not os.path.exists(completed_dir):
            ensure_directory_exists(completed_dir)
            created_count += 1
        logging.debug(f"Checked directories for {section}: {arr_dir} and {completed_dir}")
    
    return created_count

def refresh_rclone_vfs(directory_path, config):
    import_dir = config.get('DEFAULT', 'nzb_import_directory')
    rclone_vfs_url = config.get('Rclone', 'vfs_url')
    
    # Extract the relative path from nzb_import_directory
    relative_path = os.path.relpath(directory_path, import_dir)
    
    # Construct the refresh path
    refresh_path = f"/Import/{relative_path}"
    
    url = f"{rclone_vfs_url}/vfs/refresh"
    params = {
        'dir': refresh_path
    }
    try:
        response = requests.post(url, params=params)
        response.raise_for_status()
        logging.info(f"Rclone VFS refresh successful for {refresh_path}")
    except requests.RequestException as e:
        logging.error(f"Failed to refresh Rclone VFS for {refresh_path}: {e}")

def send_to_sabnzbd(nzb_path, category, config):
    try:
        api_url = f"{config['SABnzbd']['url']}/api"
        params = {
            'apikey': config['SABnzbd']['api_key'],
            'mode': 'addlocalfile',
            'name': nzb_path,
            'cat': category,
            'output': 'json'
        }
        response = requests.get(api_url, params=params)
        response.raise_for_status()
        result = response.json()
        
        if result.get('status'):
            logging.info(f"Successfully added {os.path.basename(nzb_path)} to SABnzbd with category {category}")
            os.remove(nzb_path)  # Remove the file after successful processing
        else:
            logging.error(f"Failed to add {os.path.basename(nzb_path)} to SABnzbd. Error: {result.get('error', 'Unknown error')}")
    except Exception as e:
        logging.error(f"Error sending {os.path.basename(nzb_path)} to SABnzbd: {e}")

class NZBHandler(FileSystemEventHandler):
    def __init__(self, config):
        self.config = config
        self.import_dir = config.get('DEFAULT', 'nzb_import_directory')

    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith('.nzb'):
            rel_path = os.path.relpath(event.src_path, self.import_dir)
            if not any(part.lower() == 'completed' for part in rel_path.split(os.sep)):
                logging.info(f"New NZB file detected: {event.src_path}")
                process_nzb_file(event.src_path, self.config)

def process_nzb_file(nzb_path, config):
    filename = os.path.basename(nzb_path)
    subdirectory = os.path.basename(os.path.dirname(nzb_path))
    
    def attempt_processing(retry_count=0):
        try:
            is_compatible = is_compatible_nzb(nzb_path)
            logging.debug(f"Is {filename} compatible? {is_compatible}")
            
            if is_compatible:
                logging.info(f"{filename} is compatible. Processing...")
                
                # Move compatible file to completed directory
                completed_dir = os.path.join(os.path.dirname(nzb_path), 'completed')
                completed_path = os.path.join(completed_dir, filename)
                try:
                    shutil.move(nzb_path, completed_path)
                    logging.info(f"Moved processed file to: {completed_path}")
                    
                    # Refresh rclone VFS for the completed directory only
                    refresh_rclone_vfs(completed_dir, config)
                    
                    logging.info(f"Processed compatible file: {filename}")
                except Exception as e:
                    logging.error(f"Failed to move processed file {nzb_path}: {e}")
            else:
                logging.info(f"{filename} is not compatible. Sending to SABnzbd.")
                send_to_sabnzbd(nzb_path, subdirectory, config)
            return True
        except Exception as e:
            if "no element found" in str(e).lower() and retry_count < 3:
                logging.warning(f"NZB file {filename} appears incomplete. Retrying in 2 seconds...")
                time.sleep(2)
                return attempt_processing(retry_count + 1)
            else:
                logging.error(f"Error processing {filename}: {e}")
                return False

    attempt_processing()

def start_monitoring(config):
    watch_directory = config.get('DEFAULT', 'nzb_import_directory')
    event_handler = NZBHandler(config)
    observer = Observer()

    observer.schedule(event_handler, watch_directory, recursive=True)
    observer.start()
    logging.info(f"Started monitoring {watch_directory}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

def process_existing_nzbs(config):
    watch_directory = config.get('DEFAULT', 'nzb_import_directory')
    logging.info("Processing existing NZB files...")
    
    for root, dirs, files in os.walk(watch_directory):
        if 'completed' in dirs:
            dirs.remove('completed')  # don't visit 'completed' directories
        for file in files:
            if file.lower().endswith('.nzb'):
                nzb_path = os.path.join(root, file)
                logging.info(f"Found existing NZB file: {nzb_path}")
                process_nzb_file(nzb_path, config)
    
    logging.info("Finished processing existing NZB files.")

def main():
    config = configparser.ConfigParser()
    config.read('config.ini')

    setup_logging(config)

    logging.info("Starting NZB Blackhole script")
    logging.info(f"Version: 1.01")
    
    watch_directory = config.get('DEFAULT', 'nzb_import_directory')
    logging.info(f"Watching directory: {watch_directory}")

    # Ensure the watch directory exists
    ensure_directory_exists(watch_directory)

    # Create subdirectories for each 'arr' service
    created_dirs = create_arr_subdirectories(config)
    if created_dirs > 0:
        logging.info(f"Created subdirectories for {created_dirs} *arr services")
    
    # Process existing NZB files
    process_existing_nzbs(config)
    
    start_monitoring(config)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("NZB Blackhole stopped by user")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        logging.exception("Stack trace:")
    finally:
        logging.info("NZB Blackhole shutting down")
