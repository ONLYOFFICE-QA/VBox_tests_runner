# -*- coding: utf-8 -*-
from dataclasses import dataclass
from os.path import isfile
from typing import Dict, List, Optional

from host_tools import File, HostInfo

from frameworks.test_data import TestData


@dataclass
class ConversionTestData(TestData):
    """
    Data class for conversion tests configuration and command generation.

    :param version: Version string to test
    :param config_path: Path to configuration file
    :param cores: Number of CPU cores to use
    :param direction: Conversion direction (e.g., 'to', 'from')
    :param telegram: Send results to Telegram
    :param t_format: Target format for conversion
    :param env_off: Disable environment setup
    :param quick_check: Run quick check mode
    :param x2t_limits: X2T process limits
    :param check_error: Check for errors mode
    :param out_x2ttester_param: Additional x2ttester output parameters
    """
    version: str
    config_path: str
    cores: Optional[int] = None
    direction: Optional[str] = None
    telegram: bool = False
    t_format: Optional[str] = None
    env_off: bool = False
    quick_check: bool = False
    x2t_limits: Optional[int] = None
    check_error: bool = False
    out_x2ttester_param: bool = False
    __status_bar: bool | None = None
    __config = None
    __restore_snapshot: bool = True
    __snapshot_name: str = None
    __configurate: bool = True
    __update_interval: int = 60


    def __post_init__(self):
        super().__post_init__()

    @property
    def status_bar(self) -> bool | None:
        return self.__status_bar

    @status_bar.setter
    def status_bar(self, value: bool):
        if not isinstance(value, bool):
            raise TypeError("status_bar must be a boolean value")
        self.__status_bar = value

    @property
    def config(self) -> dict:
        if self.__config is None:
            self.__config = self._read_config()
        return self.__config

    @property
    def restore_snapshot(self) -> bool:
        return self.__restore_snapshot

    @property
    def snapshot_name(self) -> str:
        return self.__snapshot_name

    @property
    def configurate(self) -> bool:
        return self.__configurate

    @property
    def update_interval(self) -> int:
        return self.__update_interval

    @restore_snapshot.setter
    def restore_snapshot(self, value: bool):
        if not isinstance(value, bool):
            raise TypeError("restore_snapshot must be a boolean value")
        self.__restore_snapshot = value

    @snapshot_name.setter
    def snapshot_name(self, value: str):
        if not isinstance(value, str):
            raise TypeError("snapshot_name must be a string value")
        self.__snapshot_name = value

    @configurate.setter
    def configurate(self, value: bool):
        if not isinstance(value, bool):
            raise TypeError("configurate must be a boolean value")
        self.__configurate = value

    @property
    def vm_names(self) -> List[str]:
        return [name for name in self.config.get('hosts', []) if ('macos' in name.lower()) == HostInfo().is_mac]

    def _read_config(self) -> Dict:
        if not isfile(self.config_path):
            raise FileNotFoundError(f"[red]|ERROR| Configuration file not found: {self.config_path}")
        return File.read_json(self.config_path)

    def generate_run_command(self) -> str:
        """
        Generate the run command based on configuration parameters.

        :return: Command string for running conversion tests
        """
        base_cmd = 'uv run inv conversion-test'
        args = [base_cmd, f"--version {self.version}"]

        if self.cores is not None:
            args.append(f"--cores {self.cores}")

        if self.direction:
            args.append(f"--direction {self.direction}")

        if self.telegram:
            args.append("--telegram")

        if self.t_format:
            args.append(f"--t-format {self.t_format}")

        if self.env_off:
            args.append("--env-off")

        if self.quick_check:
            args.append("--quick-check")

        if self.x2t_limits is not None:
            args.append(f"--x2t-limits {self.x2t_limits}")

        if self.check_error:
            args.append("--check-error")

        if self.out_x2ttester_param:
            args.append("--out-x2ttester-param")

        return " ".join(args)
