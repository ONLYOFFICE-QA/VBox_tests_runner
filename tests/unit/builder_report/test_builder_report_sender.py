from tests.builder_tests.builder_report_sender import BuilderReportSender
import pytest
import pandas as pd


class DummyReport:
    def __init__(self):
        self.df = None
    def read(self, path):
        return self.df
    def save_csv(self, df, path):
        pass

@pytest.fixture
def sender():
    sender = BuilderReportSender(report_path="dummy.csv")  # noqa: F821
    sender.report = DummyReport()
    return sender

def test_get_errors_only_df_all_passed(sender):
    df = pd.DataFrame([
        {"Exit_code": 0, "Stderr": "", "Version": "1.0"},
        {"Exit_code": 0, "Stderr": None, "Version": "1.0"},
    ])
    sender._BuilderReportSender__df = df
    result = sender.get_errors_only_df()
    assert result.empty

def test_get_errors_only_df_exit_code_error(sender):
    df = pd.DataFrame([
        {"Exit_code": 1, "Stderr": "", "Version": "1.0"},
        {"Exit_code": 0, "Stderr": None, "Version": "1.0"},
    ])

    sender._BuilderReportSender__df = df
    result = sender.get_errors_only_df()
    assert len(result) == 1
    assert result.iloc[0]["Exit_code"] == 1

def test_get_errors_only_df_stderr_error(sender):
    df = pd.DataFrame([
        {"Exit_code": 0, "Stderr": "error", "Version": "1.0"},
        {"Exit_code": 0, "Stderr": None, "Version": "1.0"},
    ])
    sender._BuilderReportSender__df = df
    result = sender.get_errors_only_df()
    assert len(result) == 1
    assert result.iloc[0]["Stderr"] == "error"

def test_get_errors_only_df_empty(sender):
    df = pd.DataFrame([], columns=["Exit_code", "Stderr", "Version"])
    sender._BuilderReportSender__df = df
    result = sender.get_errors_only_df()
    assert result is None

def test_get_errors_only_df_none(sender):
    sender._BuilderReportSender__df = None
    result = sender.get_errors_only_df()
    assert result is None
