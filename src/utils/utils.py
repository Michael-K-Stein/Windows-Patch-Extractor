import argparse
import os
import re
from types import NoneType
from typing import Callable

import requests
import tqdm
from src.utils.printer import printError, printLog
from src.utils.tmps import TmpDir as TmpDir
from src.utils.settings import *


class SymbolManagerException(Exception):
    pass


def __walkFilesInternal(
    root: str,
    current_dir: str,
    callback: Callable[[str, str], NoneType],
    file_name_regex: str | re.Pattern[str],
    recursive: bool = True
) -> NoneType:
    """
    Internal function for recursively walking files in a directory and applying a callback function.

    Args:
        root (str): The root directory to start the search from.
        current_dir (str): The current directory being processed.
        callback (Callable[[str, str], NoneType]): The callback function to apply to matching files.
        file_name_regex (str | re.Pattern[str]): A regular expression pattern to match file names.
        recursive (bool, optional): Whether to search for files recursively. Defaults to True.

    Returns:
        NoneType: The function returns nothing.
    """
    for r, ds, fs in os.walk(current_dir):
        if recursive and False:
            for d in ds:
                # Recursively walk subdirs
                p = os.path.join(r, d)
                __walkFilesInternal(root, p, callback, file_name_regex, True)
        for f in fs:
            # If a file name regex was specified but does not match, skip
            if file_name_regex and (not re.search(file_name_regex, f, re.I)):
                continue
            p = os.path.join(r, f)
            callback(root, p)


def walkFiles(root: str, callback: Callable[[str, str], NoneType], file_name_regex: str | re.Pattern[str], recursive: bool = True) -> NoneType:
    """
    Recursively walks through files in a directory and applies a callback function to matching files.

    Args:
        root (str): The root directory to start the search from.
        callback (Callable[[str, str], NoneType]): A callback function that takes two string arguments
            (full file path and file name) and returns None.
        file_name_regex (str | re.Pattern[str]): A regular expression pattern (str or compiled pattern)
            to match file names.
        recursive (bool, optional): If True (default), the function searches for files recursively
            in subdirectories; if False, it only searches in the root directory.

    Returns:
        NoneType: This function returns nothing.

    Example:
        To print the names of all text files in a directory and its subdirectories:

        ```python
        import re

        def print_text_files(full_path, file_name):
            if re.search(r'\.txt$', file_name):
                print(file_name)

        walkFiles('/path/to/directory', print_text_files, r'.*\.txt$')
        ```
    """
    __walkFilesInternal(root, root, callback, file_name_regex, recursive)


def validateFilePath(file_path):
    if not os.path.exists(file_path):
        raise argparse.ArgumentTypeError(f"'{file_path}' is neither a file nor a directory!")  
    return file_path


def validateFilePathDir(file_path):
    fp = validateFilePath(file_path)
    if not os.path.isdir(fp):
        raise argparse.ArgumentTypeError(f"'{file_path}' is not a directory!")
    return fp


def validateRegex(pattern):
    try:
        a = re.compile(pattern)
        return pattern
    except re.error as e:
        raise argparse.ArgumentTypeError(f"Invalid regular expression: {e}")


def setOutputDirectory(new_dir: str, allow_implicit_dir_creation: bool) -> NoneType:
    getSettings().s_output_dir = new_dir
    if not os.path.exists(getOutputDirectory()):
        if not allow_implicit_dir_creation and not confirm_action(f'Output directory does not exist. Would you like to create it now?'):
            exit(-1)
        printLog(f'Creating directory tree {getOutputDirectory()}')
        os.makedirs(getOutputDirectory())
    if not os.path.isdir(getOutputDirectory()):
        printError(f'Output directory is not a directory!')
        exit(-2)


def downloadFileWithProgress(url: str, fileName: str):
    response = requests.get(url, stream=True)

    totalSizeInBytes = int(response.headers.get('content-length', 0))
    blockSize = 1024  # 1 Kibibyte

    progressBar = tqdm.tqdm(total=totalSizeInBytes, unit='iB', unit_scale=True, colour='yellow')

    with open(fileName, 'wb') as file:
        for data in response.iter_content(blockSize):
            progressBar.update(len(data))
            file.write(data)

    progressBar.close()

    if totalSizeInBytes != 0 and progressBar.n != totalSizeInBytes:
        printError("ERROR, something went wrong")


def normalizeDirtyBitness(dirty_bitness: str) -> str:
    if dirty_bitness == 'amd64':
        return 'x64'
    if dirty_bitness == 'msil':
        return 'msil'
    if dirty_bitness == 'x64' or dirty_bitness == 'x86':
        return dirty_bitness
    if dirty_bitness == 'wow64':
        return dirty_bitness
    raise SymbolManagerException(f'Bitness "{dirty_bitness}" is not recognized!')


def monthToNumber(monthName: str) -> str | int:
    """Translate month name to month number."""
    monthDict = {
        'January': 1,
        'February': 2,
        'March': 3,
        'April': 4,
        'May': 5,
        'June': 6,
        'July': 7,
        'August': 8,
        'September': 9,
        'October': 10,
        'November': 11,
        'December': 12
    }
    return monthDict.get(monthName, "Invalid month name")
