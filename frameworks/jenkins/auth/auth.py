from pathlib import Path


class Auth:
    CONFIG_DIR: Path = Path.home() / ".jenkins"
    TOKEN_FILE: Path = CONFIG_DIR / "token"
    ID_FILE: Path = CONFIG_DIR / "id"

    def __init__(self, id: str = None, token: str = None):
        self.id = id or self._get_id()
        self.token = token or self._get_token()

    def _get_token(self) -> str:
        return self.TOKEN_FILE.read_text().strip()

    def _get_id(self) -> str:
        return self.ID_FILE.read_text().strip()
