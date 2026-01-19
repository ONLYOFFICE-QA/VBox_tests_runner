from pathlib import Path


class Auth:
    CONFIG_DIR: Path = Path.home() / ".jenkins"
    TOKEN_FILE: Path = CONFIG_DIR / "token"
    ID_FILE: Path = CONFIG_DIR / "id"

    def __init__(self, id: str = None, token: str = None):
        self.id = id or self._get_id()
        self.token = token or self._get_token()

    def _get_token(self) -> str:
        if not self.TOKEN_FILE.is_file():
            raise FileNotFoundError(f"|ERROR| Token file not found: {self.TOKEN_FILE}")
        token = self.TOKEN_FILE.read_text().strip()
        if not token:
            raise ValueError(f"|ERROR| Token file is empty: {self.TOKEN_FILE}")
        return token

    def _get_id(self) -> str:
        if not self.ID_FILE.is_file():
            raise FileNotFoundError(f"|ERROR| ID file not found: {self.ID_FILE}")
        id = self.ID_FILE.read_text().strip()
        if not id:
            raise ValueError(f"|ERROR| ID file is empty: {self.ID_FILE}")
        return id
