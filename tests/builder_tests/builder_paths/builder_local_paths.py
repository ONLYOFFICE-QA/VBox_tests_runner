# -*- coding: utf-8 -*-
from os.path import join
from tempfile import gettempdir

from host_tools import File

from frameworks.test_data.paths import LocalPaths


class BuilderLocalPaths(LocalPaths):
    """
    Defines paths specific to the builder testing process. Inherits common paths from LocalPaths.

    Attributes:
        dep_test (str): Name of the Dep.Tests directory (used as a reference name).
        dep_test_path (str): Full path to the Dep.Tests folder.
        docbuilder_path (str): Full path to the 'docbuilder' directory inside Dep.Tests.
        dep_test_archive (str): Path to the zip archive of Dep.Tests created in the temp directory.
        docbuilder_config (str): Path to the config.json file inside the docbuilder directory.
        document_builder_samples (str): Path to the 'document-builder-samples' directory inside docbuilder.
        build_tools (str): Name of the build_tools directory.
        build_tools_path (str): Full path to the cloned build_tools repository.
        build_tools_archive (str): Path to the zip archive of build_tools.
        office_js_api (str): Name of the office-js-api directory.
        office_js_api_path (str): Full path to the cloned office-js-api repository.
        office_js_api_archive (str): Path to the zip archive of office-js-api.
        builder_report_dir (str): Path to the directory where builder-related test reports will be saved.
    """
    dep_test: str = 'Dep.Tests'
    dep_test_path: str = join(File.unique_name(gettempdir()), dep_test)
    docbuilder_path: str = join(dep_test_path, 'docbuilder')
    dep_test_archive: str = join(LocalPaths.tmp_dir, f"{dep_test}.zip")
    docbuilder_config: str = join(docbuilder_path, 'config.json')
    document_builder_samples: str = join(docbuilder_path, "document-builder-samples")

    build_tools: str = 'build_tools'
    build_tools_path: str = join(File.unique_name(gettempdir()), build_tools)
    build_tools_archive: str = join(LocalPaths.tmp_dir, f"{build_tools}.zip")

    office_js_api: str = 'office-js-api'
    office_js_api_path: str = join(File.unique_name(gettempdir()), office_js_api)
    office_js_api_archive: str = join(LocalPaths.tmp_dir, f"{office_js_api}.zip")

    builder_report_dir = join(LocalPaths.reports_dir, 'Builder_tests')
