# -*- coding: utf-8 -*-


class SchtasksCommand:

    def __init__(self, task_name: str):
        self.task_name = task_name

    def status(self) -> str:
        return f'schtasks /query /tn "{self.task_name}" /v /fo LIST'

    def create(self, command: str) -> str:
        return f'schtasks /create /tn "{self.task_name}" /tr "{command}" /sc onstart /rl highest'

    def run(self) -> str:
        return f'schtasks /run /tn "{self.task_name}"'
