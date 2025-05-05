# VBox tests runner

## Description

A project for running tests inside Vbox virtual machines

## Requirements

* Python 3.11
* VBox 7
* [Python package manager: uv](https://docs.astral.sh/uv/)

## Installing uv

```
pip install uv
```

## Desktop tests

### desktop_tests_config.json parameters

`desktop_script`[required] - link to a repository with a script to run in a virtual machine

`branch`[optional] - branch from which the script will be downloaded. (default is 'master')

`token_file`[optional] - name of the file containing the telegram token
located at `~/.telegram` folder. (default is 'token')

`chat_id_file`[optional] - name of the file containing the telegram chat id
located at `~/.telegram` folder. (default is 'chat')

`password`[optional] - password from the virtual machine user.

`hosts`[required] - array with names of virtual machines to run tests

## Desktop tests Commands

`uv run inv desktop-test` - To run desktop editors tests

### Desktop-test flags

`--version` or `-v`[required] - Specifies the version of DesktopEditor.

`--headless` or `-h`[optional] - To run virtual machines in the background

`--processes` or `-p`[optional] - Number of threads. to run tests in multithreaded mode (default is '1')

`--name` or `-n`[optional] - Name of the virtual machine to selectively run tests

`--connect-portal` or `-c`[optional] - Report upload to report-portal


## Builder tests

### builder_tests_config.json parameters

`dep_test_branch`[optional] - branch from which the script will be downloaded. (default is 'master')

`build_tools_branch`[optional] - branch from which the script will be downloaded. (default is 'master')

`office_js_api_branch`[optional] - branch from which the script will be downloaded. (default is 'master')

`document_builder_samples`[optional] - branch from which the script will be downloaded. (default is 'master')

`token_file`[optional] - name of the file containing the telegram token
located at `~/.telegram` folder. (default is 'token')

`chat_id_file`[optional] - name of the file containing the telegram chat id
located at `~/.telegram` folder. (default is 'chat')

`password`[optional] - password from the virtual machine user.

`hosts`[required] - array with names of virtual machines to run tests

## Builder tests Commands

`uv run inv builder-test` - To run desktop editors tests

### Builder-test flags

`--version` or `-v`[required] - Specifies the version of docbuilder.

`--headless` or `-h`[optional] - To run virtual machines in the background

`--processes` or `-p`[optional] - Number of threads. to run tests in multithreaded mode (default is '1')

`--name` or `-n`[optional] - Name of the virtual machine to selectively run tests

`--connect-portal` or `-c`[optional] - Report upload to report-portal

`telegram` or `-t`[optional] - Sending a report to Telegram
