# -*- coding: utf-8 -*-
from os.path import splitext
from tempfile import gettempdir

from host_tools import File

from .puppeteer_paths import PuppeteerPaths
from .puppeteer_test_data import PuppeteerTestData


class RunScript:
    """
    Builds the script executed on the VM: unpacks the Dep.Tests archive uploaded from the host (``puppeteer`` and
    ``tools``), creates a venv - run.py installs its python packages with ``python -m pip`` itself (safe_import) -
    and runs the tests on the Desktop Editors app (``run.py --host native``). run.py downloads the tested build
    (``nativeOptions.version``) and runs ``npm install`` itself, so the VM needs Node.js with npm and internet access.

    The setup steps stop the script on the first error. Whatever run.py ends with, ``puppeteer/out`` (with the
    run.py output in ``out/vm_run.log``) is packed into ``out_archive`` for the host, and the script exits with
    the exit code of run.py.

    PowerShell (``.ps1``) and bash are supported; Windows Vista (``.bat``) has no Node.js 20.
    """

    run_log_name: str = 'vm_run.log'

    def __init__(self, test_data: PuppeteerTestData, paths: PuppeteerPaths):
        self.data = test_data
        self._path = paths
        self.is_ps1 = self._path.remote.run_script_name.endswith('.ps1')
        if not self.is_ps1 and not self._path.remote.run_script_name.endswith('.sh'):
            raise ValueError(f"Unsupported run script for puppeteer tests: {self._path.remote.run_script_name}")

    def generate(self) -> str:
        commands = [
            self.get_shebang(),
            self.get_fail_fast_command(),
            *self.get_unpack_commands(),
            *self.get_create_venv_commands(),
            self.get_change_dir_command(self._path.remote.engine_path),
            *self.get_env_commands(),
            self.get_create_dir_command(self._path.remote.out_dir),
            *self.get_run_tests_commands(),
            self.get_copy_app_log_command(),
            self.get_create_dir_command(self._path.remote.out_archive_dir),
            self.get_change_dir_command(self._path.remote.puppeteer_path),
            self.get_pack_out_command(),
            self.get_exit_on_error_command(),
            'exit $code' if self.is_ps1 else 'exit "$code"',
        ]
        return '\n'.join(line.strip() for line in filter(None, commands))

    def get_shebang(self) -> str:
        return '' if self.is_ps1 else '#!/bin/bash'

    def get_fail_fast_command(self) -> str:
        """bash stops on a failed step; pipefail gives a pipeline the exit code of its command, not of tee."""
        return '' if self.is_ps1 else 'set -eo pipefail'

    def get_exit_on_error_command(self) -> str:
        """PowerShell 5.1 does not stop on a failed native command: check its exit code."""
        return 'if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }' if self.is_ps1 else ''

    def get_unpack_commands(self) -> list[str]:
        """PowerShell unpacks with .NET: Expand-Archive needs PowerShell 5, Windows 8.1 has 4."""
        archive, destination = self._path.remote.dep_test_archive, self._path.remote.dep_test_path
        if self.is_ps1:
            return [
                "Add-Type -AssemblyName System.IO.Compression.FileSystem",
                f"if (Test-Path '{destination}') {{ Remove-Item '{destination}' -Recurse -Force -ErrorAction Stop }}",
                f"[IO.Compression.ZipFile]::ExtractToDirectory('{archive}', '{destination}')",
            ]
        return [f"unzip -q -o {archive} -d {destination}"]

    def get_change_dir_command(self, dir_path: str) -> str:
        if self.is_ps1:
            return f"Set-Location -Path '{dir_path}' -ErrorAction Stop"
        return f"cd {dir_path}"

    def get_create_dir_command(self, dir_path: str) -> str:
        if self.is_ps1:
            return f"New-Item -ItemType Directory -Force -Path '{dir_path}' -ErrorAction Stop | Out-Null"
        return f"mkdir -p {dir_path}"

    def get_venv_python(self) -> str:
        if self.is_ps1:
            return f"{self._path.remote.venv_path}/Scripts/python.exe"
        return f"{self._path.remote.venv_path}/bin/python"

    def get_create_venv_commands(self) -> list[str]:
        """
        The venv of the first python 3.9+ that makes one, in the order the VM preparation checks them:
        on Linux python3.13 ... python3.9, then python3 - an old distribution keeps its own python3 and gets a
        newer python3.x in /usr/local/bin -; on Windows every python.exe of PATH in its order (a newer one of
        the user PATH comes after an older one of the system PATH, the Store alias fails the check).
        """
        venv = self._path.remote.venv_path
        if self.is_ps1:
            return [
                "$python = $null",
                "foreach ($command in @(Get-Command python.exe -All -ErrorAction SilentlyContinue)) {",
                "& $command.Path -c 'import sys, lzma, ssl; sys.exit(sys.version_info < (3, 9))' 2>$null | Out-Null",
                f"if ($LASTEXITCODE -eq 0) {{ & $command.Path -m venv '{venv}'; "
                "if ($LASTEXITCODE -eq 0) { $python = $command.Path; break } }",
                "}",
                "if (-not $python) { Write-Output '|ERROR| no python 3.9+ with lzma and ssl that makes a venv in PATH'; exit 1 }",
                "Write-Output \"|INFO| python: $python\"",
            ]
        return [
            'python=""',
            "for candidate in python3.13 python3.12 python3.11 python3.10 python3.9 python3; do",
            'command -v "$candidate" >/dev/null 2>&1 || continue',
            "\"$candidate\" -c 'import sys, lzma, ssl; sys.exit(sys.version_info < (3, 9))' 2>/dev/null || continue",
            f'rm -rf {venv}',
            f'if "$candidate" -m venv {venv}; then python=$(command -v "$candidate"); break; fi',
            "done",
            'if [ -z "$python" ]; then echo "|ERROR| no python 3.9+ with lzma and ssl that makes a venv in PATH"; exit 1; fi',
            'echo "|INFO| python: $python"',
        ]

    def get_env_commands(self) -> list[str]:
        """
        CI=true: run.py skips syncing the editor sources (sdkjs, web-apps...) - the tests do not read them.
        PUPPETEER_SKIP_DOWNLOAD=true: the npm install of puppeteer does not download Chrome - the native host
        drives the Desktop Editors app (run.py sets it only after its own npm install).
        PYTHONIOENCODING=utf-8 and, in PowerShell, a UTF-8 console: the output of run.py reaches the log as
        UTF-8 whatever the code page of the VM (PowerShell decodes native output with the console encoding).
        On Linux the app needs the desktop session of the logged user: the script runs as a systemd service, so
        XDG_RUNTIME_DIR and the X authority file of the session are found here (``~/.Xauthority``, GDM, Xwayland
        of GNOME, SDDM).
        """
        env = {'CI': 'true', 'PUPPETEER_SKIP_DOWNLOAD': 'true', 'PYTHONIOENCODING': 'utf-8'}
        if self.is_ps1:
            return [
                *[f"$env:{name} = '{value}'" for name, value in env.items()],
                "try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch { }",
            ]
        return [
            *[f"export {name}={value}" for name, value in env.items()],
            "export DISPLAY=${DISPLAY:-:0}",
            'uid=$(id -u)',
            'if [ -z "${XDG_RUNTIME_DIR:-}" ] && [ -d "/run/user/$uid" ]; then export XDG_RUNTIME_DIR="/run/user/$uid"; fi',
            'if [ -z "${XAUTHORITY:-}" ]; then',
            'for auth in "$HOME/.Xauthority" "/run/user/$uid/gdm/Xauthority" /run/user/$uid/.mutter-Xwaylandauth.* /run/user/$uid/xauth_* /tmp/xauth_*; do',
            'if [ -f "$auth" ] && [ -O "$auth" ]; then export XAUTHORITY="$auth"; break; fi',
            'done',
            'fi',
        ]

    def get_run_tests_commands(self) -> list[str]:
        """
        run.py with its output both in the script log and in ``out/vm_run.log`` (UTF-8), its exit code in ``code``.
        A failure of run.py does not stop the script: ``out`` is packed for the host anyway.
        PowerShell 5.1 wraps each stderr line of a native command into an error record (``"$_"`` keeps the line
        only), and its Tee-Object writes UTF-16: the log is written with a StreamWriter.
        """
        log_file = f"{self._path.remote.out_dir}/{self.run_log_name}"
        command = ' '.join(self.get_run_py_args())
        if self.is_ps1:
            return [
                f"$log = New-Object System.IO.StreamWriter('{log_file}', $false, (New-Object System.Text.UTF8Encoding($false)))",
                f"{command} 2>&1 | ForEach-Object {{ $line = \"$_\"; $log.WriteLine($line); $log.Flush(); $line }}",
                "$code = $LASTEXITCODE",
                "$log.Close()",
            ]
        return [
            'set +e',
            f"{command} 2>&1 | tee {log_file}",
            'code=${PIPESTATUS[0]}',
            'set -e',
        ]

    def get_copy_app_log_command(self) -> str:
        """
        What the app printed at its last start (engine/script/js/native/localApp.js writes it to the temp folder,
        anew at each start) goes into ``out/`` with the results: the temp folder is lost with the snapshot.
        """
        name = 'desktop-editors-native.log'
        if self.is_ps1:
            return (f"Copy-Item (Join-Path $env:TEMP '{name}') '{self._path.remote.out_dir}' "
                    "-ErrorAction SilentlyContinue")
        return f'cp "${{TMPDIR:-/tmp}}/{name}" {self._path.remote.out_dir}/ 2>/dev/null || true'

    def get_pack_out_command(self) -> str:
        """Zip ``out`` (from the puppeteer folder, so the entries start with ``out/``) with the venv python."""
        return f"{self._call(self.get_venv_python())} -m zipfile -c {self._quote(self._path.remote.out_archive)} out"

    def get_run_py_args(self) -> list[str]:
        config_params = [
            f"nativeOptions.version={self.data.version}",
            f"nativeOptions.formatsFile={self._path.remote.formats_file}",
            *self.data.config_params,
        ]
        target = [self.data.test_path] if self.data.test_path else ['--suite', self.data.suite]
        return [
            self._call(self.get_venv_python()),
            'run.py',
            *target,
            '--host', 'native',
            '--disable_animation',
            '--out_directory', 'out',
            *self.data.run_options,
            '--config_params', *[f'"{param}"' for param in config_params],
        ]

    def get_save_path(self) -> str:
        return File.unique_name(gettempdir(), extension=splitext(self._path.remote.run_script_name)[1])

    def create(self) -> str:
        save_path = self.get_save_path()
        File.write(save_path, self.generate(), newline='')
        return save_path

    def _call(self, executable: str) -> str:
        return f"& '{executable}'" if self.is_ps1 else executable

    def _quote(self, path: str) -> str:
        return f"'{path}'" if self.is_ps1 else path
