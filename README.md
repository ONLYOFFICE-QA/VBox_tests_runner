# VBox Tests Runner

## 📚 Table of Contents

* [Description](#description)
* [Requirements](#requirements)
* [Installing](#installing)
* [VM Configuration](#vm-configuration)
  * [vm_config.json Parameters](#vmconfigjson-parameters)
* [Desktop Tests](#desktop-tests)
  * [desktop_tests_config.json Parameters](#desktop_tests_configjson-parameters)
  * [Desktop Test Commands](#desktop-test-commands)
  * [Desktop-test Flags](#desktop-test-flags)
* [Builder Tests](#builder-tests)
  * [builder_tests_config.json Parameters](#builder_tests_configjson-parameters)
  * [Builder Test Commands](#builder-test-commands)
  * [Builder-test Flags](#builder-test-flags)
* [Sending Messages to Telegram](#sending-messages-to-telegram)
---

## Description

A project for running tests inside VirtualBox virtual machines.

## Requirements

* Python 3.12
* VirtualBox 7.1.6
* [Python package manager: uv](https://docs.astral.sh/uv/)

## Installing

1. Install the `uv` package manager:

   ```bash
   pip install uv
   ```

2. Download or create VirtualBox virtual machines for testing.

3. Configure `./vm_configs/vm_config.json`.
   * Specify the name of your adapter

---

## VM Configuration

### Configure the file `./vm_configs/vm_config.json`

#### Base Specifications

* **cpus** *(optional)*:
Number of virtual CPUs allocated to the VM.

* **memory** *(optional)*:
Amount of RAM in megabytes.

* **audio** *(optional)*:
Set to `false` to disable audio devices and reduce overhead.

* **nested_virtualization** *(optional)*:
Enables nested virtualization, allowing the VM to run other virtual machines.

* **speculative_execution_control** *(optional)*:
Enables protection against speculative execution
vulnerabilities (e.g., Spectre, Meltdown).

#### Network Configuration

* **connect_type** *(optional)*:
Network connection type (e.g., `bridged`).

* **adapter_name** *(required)*:
Name of the host network interface to
bridge with. Required for proper network connectivity.

---

## Desktop Tests

### desktop\_tests\_config.json Parameters

* **branch** *(optional)*:
Git branch to download the script from (default: `master`).

* **token_file** *(optional)*:
File name containing the Telegram token,
located in the `~/.telegram` directory (default: `token`).

* **chat_id_file** *(optional)*:
File name containing the Telegram chat ID,
located in the `~/.telegram` directory (default: `chat`).

* **password** *(optional)*:
Password for the virtual machine user.

* **hosts** *(required)*:
List of virtual machine names to run tests on.

### Desktop Test Commands

```bash
uv run inv desktop-test
```

### Desktop-test Flags

* `--version` or `-v` *(required)*:
Specifies the version of DesktopEditor.

* `--headless` or `-h` *(optional)*:
Runs virtual machines in the background (headless mode).

* `--processes` or `-p` *(optional)*:
Number of threads to run tests in multithreaded mode (default: `1`).

* `--name` or `-n` *(optional)*:
Name of a specific virtual machine to selectively run tests.

* `--connect-portal` or `-c` *(optional)*:
Enables report upload to Report Portal.

---

## Builder Tests

### `builder_tests_config.json` Parameters

* **dep_test_branch** *(optional)*:
Git branch from which the `dep_test`
script will be downloaded (default: `master`).

* **build_tools_branch** *(optional)*:
Git branch for downloading `build_tools` scripts (default: `master`).

* **office_js_api_branch** *(optional)*:
Git branch for downloading `office_js_api` scripts (default: `master`).

* **document_builder_samples** *(optional)*:
Git branch for downloading `document_builder_samples` (default: `master`).

* **token_file** *(optional)*:
File name containing the Telegram token,
located in the `~/.telegram` folder (default: `token`).

* **chat_id_file** *(optional)*:
File name containing the Telegram chat ID,
located in the `~/.telegram` folder (default: `chat`).

* **password** *(optional)*:
Password for the virtual machine user.

* **hosts** *(required)*:
Array of virtual machine names to run the tests on.

### Builder Test Commands

```bash
uv run inv builder-test
```

### Builder-test Flags

* `--version` or `-v` *(required)*:
Specifies the version of DocBuilder.

* `--headless` or `-h` *(optional)*:
Runs virtual machines in the background (headless mode).

* `--processes` or `-p` *(optional)*:
Amount threads to run tests in multithreaded mode (default: `1`).

* `--name` or `-n` *(optional)*:
Name of the virtual machine to selectively run tests.

---

## Sending Messages to Telegram

To enable Telegram notifications (e.g. script termination reports),
you need to create the following files in the `~/.telegram` directory:

* `token` — contains the Telegram bot token.
* `chat` — contains the Telegram chat ID (channel or user).

### Using a Proxy

To send messages via a proxy, create an additional file at
`~/.telegram/proxy.json` with the following content:

```json
{
  "login": "",
  "password": "",
  "ip": "",
  "port": ""
}
```

## Report portal connection


