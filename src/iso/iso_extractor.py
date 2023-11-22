import os
from typing import List
from src.iso.common import genericExtractFromArchive
from src.iso.wim_extractor import extractFilesFromInstallWim
from src.utils.printer import printError, printLog, printSuccess
from src.utils.tmps import TmpDir
from src.utils.utils import SymbolManagerException, walkFiles


def extractFilesFromIso(iso_path: str, output_dir: str, *file_names) -> List[str]:
    return genericExtractFromArchive(iso_path, output_dir, 'ISO', *file_names)


def extractInstallWimFromIso(iso_path: str, output_dir: str) -> str:
    install_files = extractFilesFromIso(iso_path, output_dir, r'sources\install.wim', r'sources\install.esd')
    if len(install_files) != 1:
        raise SymbolManagerException(f'An invalid amount of source files ({len(install_files)}) were found in the ISO!')
    return install_files[0]


def extractInternalSourceFiles(iso_path: str, output_dir: str, *file_names) -> List[str]:
    try:
        with TmpDir() as tmp_dir:
            install_wim = extractInstallWimFromIso(iso_path, tmp_dir)
            install_wim_path = os.path.join(tmp_dir, install_wim)
            return extractFilesFromInstallWim(install_wim_path, output_dir, *file_names)
    except SymbolManagerException as ex:
        printError(f'Failed to extract internal files: {ex}')
        return []


def extractInternalSourceFilesFromDir(iso_dir_path: str, output_dir: str, *file_names) -> List[str]:
    all_extracted_files = []
    def callback(root, path):
        all_extracted_files.extend(extractInternalSourceFiles(path, output_dir, *file_names))
    walkFiles(iso_dir_path, callback, r'\.iso$')
    printSuccess(f'Extracted {len(all_extracted_files)} files from ISO directory')
    return all_extracted_files
