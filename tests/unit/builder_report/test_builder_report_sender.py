from tests.builder_tests.builder_report_sender import BuilderReportSender
import pytest
import pandas as pd
from tests.builder_tests.builder_test_data import BuilderTestData
import os
from os.path import join, expanduser


class DummyReport:
    def __init__(self):
        self.df = None
    def read(self, path):
        return self.df
    def save_csv(self, df, path):
        pass

@pytest.fixture
def sender():
    temp_config_path = '/tmp/temp_config.json'
    with open(temp_config_path, 'w') as f:
        f.write('{"report_portal": {"project_name": "default_project"}}')

    telegram_dir = join(expanduser('~'), '.telegram')
    if not os.path.exists(telegram_dir):
        os.makedirs(telegram_dir)

    token_file_path = join(telegram_dir, 'token')
    if not os.path.isfile(token_file_path):
        with open(token_file_path, 'w') as f:
            f.write('fake_token')


    chat_file_path = join(telegram_dir, 'chat')
    if not os.path.isfile(chat_file_path):
        with open(chat_file_path, 'w') as f:
            f.write('fake_chat_id')

    test_data = BuilderTestData(version='1.0.0.0', config_path=temp_config_path)
    sender = BuilderReportSender(test_data)
    sender.report = DummyReport()

    os.remove(temp_config_path)
    if os.path.isfile(token_file_path):
        os.remove(token_file_path)

    if os.path.isfile(chat_file_path):
        os.remove(chat_file_path)
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
