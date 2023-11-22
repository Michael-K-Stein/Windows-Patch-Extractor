import os
import re
import shutil
from types import NoneType
from src.patch.delta_patch import patchFile
from src.utils.printer import printError, printLog, printSuccess
from src.utils.smart_exe import buildVersionedFileName, getBinaryFileNameWithVersion, getFileProperties
from src.utils.utils import SymbolManagerException, normalizeDirtyBitness, setOutputDirectory, walkFiles
from src.utils.settings import getOutputDirectory


def deleteEmptyDirTree(leaf: str) -> NoneType:
    d, l = os.path.split(leaf)
    if len(os.listdir(leaf)) == 0:
        shutil.rmtree(leaf)
        deleteEmptyDirTree(d)
# 11\Windows\WinSxS\amd64_microsoft-windows-os-kernel_31bf3856ad364e35_10.0.22000.194_none_674de4333985bb23\r\ntoskrnl.exe


def sortBinaries(root_dir: str, output_dir: str, file_name_regex: re.Pattern[str] = r'.*\.((exe)|(dll)|(sys))$', move_files: bool = False, recursive: bool = True):
    if not file_name_regex:
        file_name_regex = r'.*\.((exe)|(dll)|(sys))$'
    def renameBinary(root: str, binary_path: str):
        try:
            path = os.path.join(root, binary_path)
            fixed_file_name = getBinaryFileNameWithVersion(path)
            out_path = os.path.join(output_dir, fixed_file_name)
            if move_files:
                if not os.path.exists(out_path):
                    shutil.move(path, out_path)
                else:
                    os.remove(path)
                d = os.path.split(path)[0]
                deleteEmptyDirTree(d)
            else:
                shutil.copy2(path, out_path)
            printSuccess(f'Processed "{fixed_file_name}"')
        except SymbolManagerException as ex:
            printError(f'Error parsing file: {ex}')
    def extrapolateWinSxS(root: str, binary_path: str):
        try:
            path = os.path.join(root, binary_path)
            # 10.0.22000.194
            reg = re.search(r'WinSxS\\(?P<arch>\w+)_microsoft-windows-.*_\w+_(?P<full_version>((?P<win_maj>\d+)\.(?P<win_min>\d+)\.(?P<major>\d+)\.(?P<minor>\d+))).*\\r\\(?P<file_name>(\w+\.\w+))$', path)
            if not reg:
                return
            file_name = reg.group('file_name')
            full_version = reg.group('full_version')
            major = reg.group('major')
            minor = reg.group('minor')
            win_maj = reg.group('win_maj')
            win_min = reg.group('win_min')
            arch = reg.group('arch')
            arch = normalizeDirtyBitness(arch)
            base_name, ext = os.path.splitext(file_name)
            base_file = os.path.join(getOutputDirectory(), buildVersionedFileName(base_name, full_version, arch, ext))
            new_version = f'{win_maj}.{win_min}.{major}.1'
            target_file = buildVersionedFileName(base_name, new_version, arch, ext)
            patchFile(base_file, os.path.join(getOutputDirectory(), target_file), path, allow_legacy=True)
            printSuccess(f'Built {target_file} from {path}')
            if move_files:
                os.remove(path)
                deleteEmptyDirTree(os.path.split(path)[0])
        except SymbolManagerException as ex:
            printError(f'Error parsing file: {ex}')
    walkFiles(root_dir, renameBinary, file_name_regex, recursive)
    walkFiles(root_dir, extrapolateWinSxS, file_name_regex, recursive)
