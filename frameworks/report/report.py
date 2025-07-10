# -*- coding: utf-8 -*-
import csv
from os.path import dirname, isfile
from csv import reader

import pandas as pd
from host_tools.utils import Dir
from rich import print


class Report:
    def __init__(self):
        """
        Initializes the Report class and sets pandas display options.
        """
        pd.set_option('display.max_rows', None)
        pd.set_option('display.max_columns', None)
        pd.set_option("expand_frame_repr", False)

    @staticmethod
    def total_count(df: pd.DataFrame, column_name: str) -> int:
        """
        Returns the total count of non-null entries in a specified column of a DataFrame.
        :param df: The DataFrame to analyze.
        :param column_name: The name of the column to count entries in.
        :return: The count of non-null entries in the column.
        """
        return df[column_name].count()

    @staticmethod
    def value_count(df: pd.DataFrame, column_name: str) -> str:
        """
        Returns the count of unique values in a specified column of a DataFrame.
        :param df: The DataFrame to analyze.
        :param column_name: The name of the column to count unique values in.
        :return: A string representation of the count of unique values.
        """
        return df[column_name].value_counts()

    def insert_column(self, path: str, location: str, column_name: str, value: str, delimiter='\t') -> pd.DataFrame:
        """
        Inserts a new column into a CSV file at a specified location.
        :param path: The path to the CSV file.
        :param location: The location to insert the new column.
        :param column_name: The name of the new column.
        :param value: The value to fill the new column with.
        :param delimiter: The delimiter used in the CSV file.
        :return: The updated DataFrame with the new column.
        """
        df = self.read(path, delimiter=delimiter)
        if column_name not in df.columns:
            df.insert(loc=df.columns.get_loc(location), column=column_name, value=value)
        else:
            print(f"[cyan]|INFO| Column `{column_name}` already exists in `{path}`")
        return df

    def merge(self, reports: list, result_csv_path: str, delimiter='\t') -> str | None:
        """
        Merges multiple CSV files into a single CSV file.
        :param reports: A list of paths to the CSV files to merge.
        :param result_csv_path: The path to save the merged CSV file.
        :param delimiter: The delimiter used in the CSV files.
        :return: The path to the merged CSV file, or None if no files were merged.
        """
        merge_reports = [
            self.read(csv_, delimiter)
            for csv_ in reports
            if isfile(csv_) and self.read(csv_, delimiter) is not None
        ]

        if merge_reports:
            df = pd.concat(merge_reports, ignore_index=True)
            df.to_csv(result_csv_path, index=False, sep=delimiter)
            return result_csv_path

        print('[green]|INFO| No files to merge')

    @staticmethod
    def write(file_path: str, mode: str, message: list, delimiter='\t', encoding='utf-8') -> None:
        """
        Writes a message to a CSV file.
        :param file_path: The path to the CSV file.
        :param mode: The mode to open the file in ('w' for write, 'a' for append).
        :param message: The message to write to the file.
        :param delimiter: The delimiter to use in the file.
        :param encoding: The encoding to use in the file.
        """
        Dir.create(dirname(file_path), stdout=False)
        with open(file_path, mode, newline='', encoding=encoding) as csv_file:
            writer = csv.writer(csv_file, delimiter=delimiter)
            writer.writerow(message)

    @staticmethod
    def read(csv_file: str, delimiter="\t", **kwargs) -> pd.DataFrame:
        """
        Reads a CSV file into a pandas DataFrame.
        :param csv_file: Path to the CSV file.
        :param delimiter: Delimiter used in the CSV file (default is '\t').
        :return: DataFrame containing the data from the CSV file.
        """
        data = pd.read_csv(csv_file, delimiter=delimiter, **kwargs)
        last_row = data.iloc[-1]

        if last_row.isnull().all() or (last_row.astype(str).str.contains(r"[^\x00-\x7F]", regex=True).any()):
            data = data.iloc[:-1]
            data.to_csv(csv_file)

        return data

    @staticmethod
    def read_via_csv(csv_file: str, delimiter: str = "\t") -> list:
        """
        Reads a CSV file and returns its contents as a list of rows.
        :param csv_file: Path to the CSV file.
        :param delimiter: Delimiter used in the CSV file (default is '\t').
        :return: A list of rows from the CSV file.
        """
        with open(csv_file, 'r') as csvfile:
            return [row for row in reader(csvfile, delimiter=delimiter)]

    @staticmethod
    def save_csv(df: pd.DataFrame, csv_path: str, delimiter="\t") -> str:
        """
        Saves a DataFrame to a CSV file.
        :param df: The DataFrame to save.
        :param csv_path: The path to save the CSV file.
        :param delimiter: The delimiter to use in the CSV file.
        :return: The path to the saved CSV file.
        """
        df.to_csv(csv_path, index=False, sep=delimiter)
        return csv_path
