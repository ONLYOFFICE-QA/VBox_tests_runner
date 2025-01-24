# -*- coding: utf-8 -*-

class SchtasksCommand:

    def __init__(self, task_name: str):
        self.task_name = task_name

    def status(self) -> str:
        return self._build_command("query", "/v /fo LIST")

    def create(self, command: str) -> str:
        return self._build_command("create", f'/tr "{command}" /sc onstart /rl highest')

    def run(self) -> str:
        return self._build_command("run")

    def _build_command(self, action: str, additional: str = "") -> str:
        return f'schtasks /{action} /tn "{self.task_name}" {additional}'.strip()
