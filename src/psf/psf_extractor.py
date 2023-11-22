import os
import re
from typing import List, Tuple
from src.psf.psf_manifest import PsfExpressManifestTag, parsePsfExpressManifest
from src.utils.printer import printSuccess


def extractFileFromPsf(psf_file_path: str, psf_manifest_file_path: str, file_name: re.Pattern[str], output_dir: str, silent: bool = False) -> List[Tuple[PsfExpressManifestTag, str]]:
    written_patch_files : List[Tuple[PsfExpressManifestTag, str]] = []
    manifest = parsePsfExpressManifest(psf_manifest_file_path, silent=silent)
    with open(psf_file_path, 'rb') as psf_file:
        for file in manifest:
            if not re.match(file_name, file.real_file_name, re.I):
                continue
            full_path = os.path.join(output_dir, f'{file.file_name} {file.diff_type}.patch')
            os.makedirs(os.path.split(full_path)[0], exist_ok=True)
            psf_file.seek(file.offset)
            with open(full_path, 'wb') as outfile:
                outfile.write(psf_file.read(file.length))
            if not silent:
                printSuccess(f'Extracted "{full_path}"')
            written_patch_files.append((file, full_path))
    return written_patch_files
