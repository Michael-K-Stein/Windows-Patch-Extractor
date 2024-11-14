import re
import subprocess
from typing import Generator, List

import tqdm
from src.externals.proc import ExternalProcedureException, run

EXPAND_FILE_PATH = r'expand'
EXTRAC32_FILE_PATH = r'extrac32'

class ExpandCommands:
    ListFiles = '-D'
    # ExtractFilesFlat = 'e'
    # ExtractFiles = 'x'

class ExpandFlags:
    FileNames = '-F'
    IgnoreDirectoryStructure = '-I'
#     DisableProgressIndicator = '-bd'
#     OutputLogLevelHigh = '-bb3'
#     OutputLogLevelLow = '-bb0'
#     ShowTechnicalInfo = '-slt'
#     RecursiveSearch = '-r'
#     class OverwriteMode:
#         RenameNew = '-aou'


class ExpandException(ExternalProcedureException):
    pass


def runExpand(params: List[str], *args, **kwargs) -> subprocess.CompletedProcess[str]:
    return run([EXPAND_FILE_PATH, *params], *args, **kwargs)


def expandListFiles(archive_path: str, file_filters: List[str] = None, *args, **kwargs):
    if not file_filters:
        file_filters = []
    for file_filter in file_filters:
        proc = runExpand([ExpandCommands.ListFiles, archive_path, f'{ExpandFlags.FileNames}:{file_filter}'], *args, **kwargs)
        output = proc.stdout.decode()
        start_sequence = 'Copyright (c) Microsoft Corporation. All rights reserved.'
        files = output[output.index(start_sequence) + len(start_sequence):]
        reg = re.finditer(r'(\w|_|\d)+\.(cab|msu):\s+(?P<file_path>(\w+\.(?P<file_ext>(\w+))))', files)
        for file in reg:
            yield file.group('file_path')


def runExtrac32(params: List[str], *args, **kwargs) -> subprocess.CompletedProcess[str]:
    return run([EXTRAC32_FILE_PATH, *params, '|', 'more'], *args, **kwargs)

def extrac32ExtractFiles(archive_path: str, output_dir: str, flat_output_dir: bool = True, file_filters: List[str] = None, *args, **kwargs)-> List[str]:
    if not file_filters:
        file_filters = []
    proc = runExtrac32(['/A', '/E', '/L', output_dir, archive_path, *file_filters], *args, **kwargs)
    output = proc.stdout.decode()
    start_sequence = 'Copyright (c) Microsoft Corporation. All rights reserved.'
    files = output[output.index(start_sequence) + len(start_sequence):]
    regex = r'\d{2}-\d{2}-\d{4}\s+\d+:\d+:\d+(a|p)\s+----\s+[\d+,]+\s+(?P<file_path>(.*\\(\w|\.|\d)+))'
    regex = r'Extracting\s+(?P<file_path>(.*\\(\w|\.|\d)+))'
    # regex = r'Adding\s+(?P<file_path>(.*\\(\w|\.|\d)+))\s+to\s+Extraction\s+Queue'
    reg = re.finditer(regex, files)
    for file in reg:
        yield file.group('file_path')


def expandExtractFiles(archive_path: str, output_dir: str, flat_output_dir: bool = True, file_filters: List[str] = None, *args, **kwargs) -> List[str]:
    # return list(extrac32ExtractFiles(archive_path, output_dir, flat_output_dir, file_filters, *args, **kwargs))
    if not file_filters:
        file_filters = []
    flags = []
    if flat_output_dir:
        flags.append(ExpandFlags.IgnoreDirectoryStructure)

    for file_filter in tqdm.tqdm(file_filters, colour='#808080'):
        proc = runExpand([archive_path, f'{ExpandFlags.FileNames}:{file_filter}', output_dir, *flags], *args, **kwargs)
        output = proc.stdout.decode()
        start_sequence = 'Copyright (c) Microsoft Corporation. All rights reserved.'
        files = output[output.index(start_sequence) + len(start_sequence):]
        regex = r'Adding\s+(?P<file_path>(.*\\(\w|\.|\d)+))\s+to\s+Extraction\s+Queue'
        reg = re.finditer(regex, files)
        for file in reg:
            yield file.group('file_path')
