# -*- coding: utf-8 -*-
from pathlib import Path

# --- Base class with essential paths ---
class LocalPaths:
    """
    Attributes:
        PROJECT_DIR (Path): Path to the current working directory (where the script is run).
                            Consider Path(__file__).resolve().parent if the class
                            is always located in a known place relative to the project root.
        HOME_DIR (Path): Path to the user's home directory.
        TG_DIR (Path): Path to the .telegram directory in the home folder.
        TMP_DIR (Path): Path to the temporary directory 'tmp' inside the project directory.
        KNOWN_HOSTS (Path): Path to the known_hosts file in the .ssh folder.
        PROXY_CONFIG (Path): Path to the proxy.json file in the .telegram folder.
    """

    PROJECT_DIR: Path = Path.cwd()
    HOME_DIR: Path = Path.home()
    TG_DIR: Path = HOME_DIR / '.telegram'
    TMP_DIR: Path = PROJECT_DIR / 'tmp'
    KNOWN_HOSTS: Path = HOME_DIR / '.ssh' / 'known_hosts'
    PROXY_CONFIG: Path = TG_DIR / 'proxy.json'
    GITHUB_TOKEN: Path = HOME_DIR /'.github' / 'token'

    # create the temporary directory if it doesn't exist
    def __init__(self):
        self.TMP_DIR.mkdir(parents=True, exist_ok=True)
