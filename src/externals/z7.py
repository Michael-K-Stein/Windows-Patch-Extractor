import re
import subprocess
from typing import Generator, List
from src.externals.proc import ExternalProcedureException, run

Z7_BIN_PATH = r'7z'

class z7Commands:
    ListFiles = 'l'
    ExtractFilesFlat = 'e'
    ExtractFiles = 'x'

class z7Flags:
    MultiThread = '-mmt'
    DisableProgressIndicator = '-bd'
    OutputLogLevelHigh = '-bb3'
    OutputLogLevelLow = '-bb0'
    ShowTechnicalInfo = '-slt'
    RecursiveSearch = '-r'
    class OverwriteMode:
        RenameNew = '-aou'


class z7Exception(ExternalProcedureException):
    pass


def run7z(params: List[str], *args, **kwargs) -> subprocess.CompletedProcess[str]:
    return run([Z7_BIN_PATH, *params], *args, **kwargs)


def z7ListFiles(archive_path: str, file_filters: List[str] = None, *args, **kwargs):
    if not file_filters:
        file_filters = []
    proc = run7z([z7Commands.ListFiles, archive_path, z7Flags.RecursiveSearch, z7Flags.DisableProgressIndicator, z7Flags.MultiThread, z7Flags.OutputLogLevelLow, z7Flags.ShowTechnicalInfo, *file_filters], *args, **kwargs)
    output = proc.stdout.decode()
    files = output[output.index('----------'):]
    reg = re.finditer(r'Path\s*=\s*(?P<file_path>([\w\d\\\/\.\-]+))', files)
    for file in reg:
        yield file.group('file_path')


def z7ExtractFiles(archive_path: str, output_dir: str, flat_output_dir: bool = True, file_filters: List[str] = None, *args, **kwargs) -> List[str]:
    if not file_filters:
        file_filters = []
    proc = run7z([z7Commands.ExtractFilesFlat if flat_output_dir else z7Commands.ExtractFiles, archive_path, z7Flags.RecursiveSearch, z7Flags.DisableProgressIndicator, z7Flags.MultiThread, z7Flags.OutputLogLevelHigh, z7Flags.ShowTechnicalInfo, z7Flags.OverwriteMode.RenameNew, f'-o{output_dir}', *file_filters], *args, **kwargs)
    output = proc.stdout.decode()
    if 'Everything is Ok' not in output:
        raise z7Exception(output)
    if 'No files to process' in output:
        return []
    
    # Find the lines with the file names
    # Search from bottom up
    file_lines = []
    found_ok = False
    for line in output.splitlines()[::-1]:
        if not found_ok:
            if line != 'Everything is Ok':
                continue
            found_ok = True
            continue
        if not line.strip():
            # Empty line is our stop sign
            break
        file_lines.append(line)

    paths = []
    for file_line in file_lines:
        path = re.search(r'-\s+(?P<file_path>([\w\d\\\/\.\-]+))', file_line)
        if path:
            paths.append(path)
    return [p.group('file_path') for p in paths]

    # Legacy code to return the amount of files extracted
    reg = re.search(r'files\s*:\s*(?P<file_count>\d+)', output, re.I)
    if not reg or not reg.group('file_count'):
        # If exactly 1 file was extracted, it simply lists the file name :(
        if re.search(r'-\s*([\w\d\\\/\.\-]+)\s*Everything is Ok', output, re.M):
            return 1
        raise z7Exception(f'Failed to verify amount of files extracted!')
    return int(reg.group('file_count'))
