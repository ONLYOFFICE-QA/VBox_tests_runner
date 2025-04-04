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

    project_dir: Path = Path.cwd()
    home_dir: Path = Path.home()
    tg_dir: Path = home_dir / '.telegram'
    tmp_dir: Path = project_dir / 'tmp'
    known_hosts: Path = home_dir / '.ssh' / 'known_hosts'
    proxy_config: Path = tg_dir / 'proxy.json'
    github_token: Path = home_dir /'.github' / 'token'

    # create the temporary directory if it doesn't exist
    def __init__(self):
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
