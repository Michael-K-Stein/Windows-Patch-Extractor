import os
from typing import List
from src.externals.z7 import z7ExtractFiles
from src.iso.iso_extractor import genericExtractFromArchive
from src.utils.printer import printError, printLog, printSuccess
from src.utils.utils import SymbolManagerException, walkFiles

def extractFilesFromInstallWim(install_file_path: str, output_dir: str, *file_names) -> List[str]:
    ext = os.path.splitext(install_file_path)[1]
    return genericExtractFromArchive(install_file_path, output_dir, f'install.{ext}', *file_names)


def extractInternalSourceFilesFromWimDir(wim_dir_path: str, output_dir: str, *file_names) -> List[str]:
    all_extracted_files = []
    def callback(root, path):
        all_extracted_files.extend(extractFilesFromInstallWim(path, output_dir, *file_names))
    walkFiles(wim_dir_path, callback, r'\.((wim)|(esd))$')
    printSuccess(f'Extracted {len(all_extracted_files)} from WIM/ESD directory')
    return all_extracted_files
