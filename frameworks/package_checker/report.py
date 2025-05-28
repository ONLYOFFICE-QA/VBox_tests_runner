# -*- coding: utf-8 -*-
import os
import csv
from os.path import join, basename
from typing import Optional, Dict, List


class Report:
    report_path: str = join(os.getcwd(),  "report.csv")

    def __init__(self, version: str, csv_path: str = None):
        """
        Initialize report handler.

        :param csv_path: Path to the CSV file.
        :param version: Version string for filtering.
        """
        self.csv_path = csv_path or self.report_path
        self.version = version

    def load_results(
        self,
        categories: Optional[List[str]] = None,
        names: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, Dict[str, object]]]:
        """
        Load results from CSV file filtering by categories and names if provided.

        :param categories: Optional list of categories to filter.
        :param names: Optional list of package names to filter.
        :return: Nested dict {category: {name: {'url': ..., 'result': True/False}}}
        """
        if not os.path.exists(self.csv_path):
            return {}

        grouped_results: Dict[str, Dict[str, Dict[str, object]]] = {}

        with open(self.csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["Version"] != self.version:
                    continue
                category = row["Category"]
                name = row["Package_name"]

                if categories and category not in categories:
                    continue
                if names and name not in names:
                    continue

                if category not in grouped_results:
                    grouped_results[category] = {}

                result_bool = row.get("Result", "False").lower() == "true"

                grouped_results[category][name] = {
                    "url": row["URL"],
                    "result": result_bool
                }

        return grouped_results

    def save_results(
        self,
        grouped_results: Dict[str, Dict[str, Dict[str, object]]]
    ) -> None:
        """
        Save grouped results to CSV file.

        :param grouped_results: Nested dict {category: {name: {'url': ..., 'result': True/False}}}
        """
        with open(self.csv_path, mode="w", encoding="utf-8", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["Version", "Package_name", "Result", "Category", "URL"])

            for category, packages in grouped_results.items():
                for info in packages.values():
                    writer.writerow([
                        self.version,
                        basename(str(info["url"])),
                        str(info["result"]),
                        category,
                        info["url"],
                    ])

    def has_cache(
        self,
        categories: Optional[List[str]] = None,
        names: Optional[List[str]] = None
    ) -> bool:
        """
        Check if CSV cache file exists and contains entries for given filters.

        :param categories: Optional categories to check.
        :param names: Optional package names to check.
        :return: True if matching entries found, else False.
        """
        results = self.load_results(categories, names)
        return bool(results)
