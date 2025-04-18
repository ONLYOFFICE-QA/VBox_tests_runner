# -*- coding: utf-8 -*-
from os.path import join
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

    project_dir: str = str(Path.cwd())
    home_dir: str = str(Path.home())
    tg_dir: Path = join(home_dir, '.telegram')
    tmp_dir: Path = join(project_dir, 'tmp')
    known_hosts: Path = join(home_dir, '.ssh', 'known_hosts')
    proxy_config: Path = join(tg_dir, 'proxy.json')
    github_token: Path = join(home_dir, '.github', 'token')
    reports_dir: Path = join(project_dir, 'reports')
