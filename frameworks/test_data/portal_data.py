# -*- coding: utf-8 -*-
from dataclasses import dataclass, field

@dataclass
class PortalStatus:
    skipped: str = "SKIPPED"
    passed: str = "PASSED"
    failed: str = "FAILED"

@dataclass
class TestStatus:
    not_exists_package: str = "PACKAGE_NOT_EXISTS"
    failed_create_vm: str = "FAILED_CREATE_VM"
    skipped_tuple: tuple = field(init=False)

    def __post_init__(self):
        self.skipped_tuple = (self.not_exists_package, self.failed_create_vm)

@dataclass
class PortalData:

    def __post_init__(self):
        self.portal_status = PortalStatus()
        self.test_status = TestStatus()

    def get_status(self, status: str) -> str:
        _status = str(status).upper()
        if _status in self.test_status.skipped_tuple:
            return self.portal_status.skipped
        return None
