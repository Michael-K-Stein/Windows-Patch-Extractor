import os
import re
import shutil
import hashlib
import base64
from typing import List
from src.patch.dpatch import *
from src.patch.extract_msu import MsuVersion, extractMsu
from src.psf.psf_manifest import PsfExpressManifestTag
from src.utils.printer import printError, printInfo, printLog, printSuccess
from src.utils.settings import getInterestingFilesAsRegex, getOutputDirectory
from src.utils.smart_exe import buildVersionedFileName
from src.utils.tmps import TmpDir
from src.utils.utils import normalizeDirtyBitness, walkFiles


def patchFile(input_file, output_file, *patch_files, allow_legacy: bool = True) -> bytes:
    dry_run = output_file is None

    if input_file is None:
        inbuf = b""
    else:
        with open(input_file, 'rb') as r:
            inbuf = r.read()

    buf = cast(inbuf, wintypes.LPVOID)
    n = len(inbuf)
    to_free = []
    try:
        for patch in patch_files:
            buf, n = apply_patchfile_to_buffer(buf, n, patch, allow_legacy)
            to_free.append(buf)

        outbuf = bytes((c_ubyte*n).from_address(buf))
        if not dry_run:
            with open(output_file, 'wb') as w:
                w.write(outbuf)
    finally:
        for buf in to_free:
            DeltaFree(buf)
    
    return outbuf


def handleExtrapolatePatch(args):
    if args.null:
        input_file = None
    else:
        input_file = args.file

    if args.dry_run:
        output_file = None
    else:
        output_file = args.output_file

    outbuf = patchFile(input_file, output_file, *args.patches, allow_legacy=args.legacy)

    finalhash = hashlib.sha256(outbuf)
    printSuccess("Applied {} patch{} successfully"
          .format(len(args.patches), "es" if len(args.patches) > 1 else ""))
    printSuccess(f"Final hash: {finalhash.hexdigest()}")


def guessBitnessForPatchFile(manifest: PsfExpressManifestTag) -> str:
    reg = re.search(r'^(?P<bitness>((amd64)|(x(64|86))|(wow64)|(msil)))_', manifest.file_name)
    if not reg:
        return 'x00'
    arch = reg.group('bitness')
    arch = normalizeDirtyBitness(arch)
    return arch


def createBaseFileFromReverse(base_files_dir: str, base_file_name: str, extension: str, target_version: str, base_version: str, bitness: str, kb: str, patch_file: str) -> bool:
    if extension[0] != '.':
        extension = '.' + extension

    bitness = normalizeDirtyBitness(bitness)
    base_versioned_name = buildVersionedFileName(base_file_name, base_version, bitness, extension)

    at_least_one_file_found = False
    def handleFile(root, path: str):
        global at_least_one_file_found
        at_least_one_file_found = True
        try:
            patchFile(path, os.path.join(base_files_dir, base_versioned_name), patch_file, allow_legacy=True)
            printSuccess(f'Built base {base_versioned_name} from reverse patch')
        except SymbolManagerException as ex:
            printLog(f'Error creating base from reverse: {ex}')
        return True

    bitness_regex = re.escape(bitness)
    if bitness.lower() == 'wow64':
        # There is a bug in "sort" which replaces "wow64" with "x86".
        # We can safely handle this here since we always verify the hash
        #  this file name regex only filters which files to even check.
        bitness_regex = r'(wow64|x86)'
    if '_' in base_file_name:
        base_file_name_regex = r'((' + base_file_name + r')|(' + base_file_name.split('_')[0] + r'))'
    file_name_regex = r'^' + re.escape(base_file_name) + r'\s+.*\s*' + re.escape(target_version) + r'\s+.*\s*' + bitness_regex + r'(\s+-\s+((KB\d+)|(\d+-\d+-\d+)))?.*' + re.escape(extension)
    # Search both the given base files dir and the output directory
    for base_dir in set([base_files_dir, getOutputDirectory()]):
        printLog(f'Searching for file {file_name_regex}')
        walkFiles(base_dir, handleFile, file_name_regex=file_name_regex)
    
    if not at_least_one_file_found:
        printLog(f'No files matched "{file_name_regex}" to create reverse base!')
        return False

    return True


def doPatchOrCreateBase(base_files_dir: str, base_file_name: str, extension: str, target_version: str, base_version: str, bitness: str, kb: str, patch_direction: str, patch_file: str):
    bitness = normalizeDirtyBitness(bitness)
    base_versioned_name = buildVersionedFileName(base_file_name, base_version, bitness, extension)
    target_versioned_name = buildVersionedFileName(base_file_name, target_version, bitness, extension, kb)

    base_file = os.path.join(base_files_dir, base_versioned_name)
    if not os.path.exists(base_file) and bitness == 'wow64':
        base_versioned_name = buildVersionedFileName(base_file_name, base_version, 'x86', extension)
        base_file = os.path.join(base_files_dir, base_versioned_name)

    if not os.path.exists(base_file):
        # No base file, we cannot do the patch!
        # If this a reverse patch, try to create the base file
        if patch_direction == 'r':
            printLog(f'Trying reverse...')
            if not createBaseFileFromReverse(base_files_dir, base_file_name, extension, target_version, base_version, bitness, kb, patch_file):
                raise SymbolManagerException(f'Base file both not found & was not able to be created!')
            printSuccess(f'Built reverse base file {base_versioned_name}')
            # We created the base file, and that is all we shall do with the reverse patch :)
            return
        raise SymbolManagerException(f'Base file "{base_versioned_name}" not found!')

    if os.path.exists(os.path.join(getOutputDirectory(), target_versioned_name)):
        printLog(f'Skipping {target_versioned_name}')
        return

    if patch_direction == 'n':
        patchFile(None, os.path.join(getOutputDirectory(), target_versioned_name), patch_file, allow_legacy=True)
    else:
        patchFile(base_file, os.path.join(getOutputDirectory(), target_versioned_name), patch_file, allow_legacy=True)
    printSuccess(f'Built patched file {target_versioned_name}')


def extrapolateMsuFile(msu_file, args):
    regex_name = args.name
    if not regex_name:
        regex_name = getInterestingFilesAsRegex()
    printLog(f'Extracting files matching "{regex_name}"')
    with TmpDir() as patch_files_dir:
        r = extractMsu(msu_file, regex_name, patch_files_dir, silent=True)
        if r[0] == MsuVersion.WinServer:
            _, kb, extracted_files = r
            extrapolateMsuWindowsServerFile(kb, extracted_files, args)
            return
        elif r[0] == MsuVersion.Win10:
            _, kb, extracted_files = r
            extrapolateMsuWindowsLegacyFile(kb, extracted_files, args)
            return
        else:
            _, msu_metadata, kb, files = r

        base_files_dir = args.base_files_dir

        for man, path in files:
            try:
                bitness = guessBitnessForPatchFile(man)
                base_name, ext = os.path.splitext(man.real_file_name)
                versioned_file_name = buildVersionedFileName(base_name, msu_metadata.os_base_version, bitness, ext)
                target_versioned_file_name = buildVersionedFileName(base_name, msu_metadata.os_target_version, bitness, ext, kb)
                if os.path.exists(os.path.join(getOutputDirectory(), target_versioned_file_name)):
                    printLog(f'Skipping {target_versioned_file_name}')
                    continue
                printLog(f'{man.real_file_name} => {versioned_file_name}')

                doPatchOrCreateBase(
                    base_files_dir=base_files_dir, 
                    base_file_name=base_name, 
                    extension=ext, 
                    target_version=msu_metadata.os_target_version, 
                    base_version=msu_metadata.os_base_version, 
                    bitness=bitness, 
                    kb=kb, 
                    patch_direction='f', 
                    patch_file=path
                )

                printSuccess(f'Built patched file {target_versioned_file_name}')
            except SymbolManagerException as ex:
                printError(f'Failed to extrapolate file! {str(ex)}')


def extrapolateMsuWindowsServerFile(kb: str, extractedFiles: List[str], args):
    base_files_dir = args.base_files_dir

    patch_file_regex = r'(?P<dirty_bitness>(amd64|wow64|msil|x(86|64)))_microsoft-.*_(?P<verbose_build>((?P<verbose_build_no_patch>(\d+\.\d+\.(?P<build_major>\d+)\.))(?P<build_patch>\d+)))(_\w+)+\\(?P<patch_direction>(r|f|n))\\(?P<file_name>((?P<file_base_name>\w+)(?P<file_name_ext>(\.\w+))))$'

    for extracted_file in extractedFiles:
        try:
            reg = re.search(patch_file_regex, extracted_file)
            if not reg:
                raise SymbolManagerException(f'Extracted file does not meet name regex pattern! {extracted_file}')

            bitness = normalizeDirtyBitness(reg.group('dirty_bitness'))
            file_name = reg.group('file_name')
            base_name = reg.group('file_base_name')
            ext = reg.group('file_name_ext')
            os_target_version = reg.group('verbose_build')
            os_base_version = reg.group('verbose_build_no_patch') + '1'
            patch_direction = reg.group('patch_direction')
            build_major = reg.group('build_major')
            build_patch = reg.group('build_patch')

            printLog(f'Filename: {extracted_file}')

            doPatchOrCreateBase(
                base_files_dir=base_files_dir, 
                base_file_name=base_name, 
                extension=ext, 
                target_version=os_target_version, 
                base_version=os_base_version, 
                bitness=bitness, 
                kb=kb, 
                patch_direction=patch_direction, 
                patch_file=extracted_file
            )

        except SymbolManagerException as ex:
            printError(f'Failed to extrapolate file! {str(ex)}')


def extrapolateMsuWindowsLegacyFile(kb: str, extractedFiles: List[str], args):
    printLog(f'Extrapolating files as legacy patch')
    patch_file_regex = r'(?P<dirty_bitness>(amd64|wow64|msil|x(86|64)))_(microsoft|windows)-.*_(?P<verbose_build>((?P<verbose_build_no_patch>(\d+\.\d+\.(?P<build_major>\d+)\.))(?P<build_patch>\d+)))(_\w+)+\\(?P<file_name>((?P<file_base_name>\w+)(?P<file_name_ext>(\.\w+))))$'
    for extracted_file in extractedFiles:
        try:
            reg = re.search(patch_file_regex, extracted_file)
            if not reg:
                raise SymbolManagerException(f'Extracted file does not meet name regex pattern (Legacy style)! {extracted_file}')
            
            bitness = normalizeDirtyBitness(reg.group('dirty_bitness'))
            base_name = reg.group('file_base_name')
            ext = reg.group('file_name_ext')
            os_target_version = reg.group('verbose_build')
            target_versioned_file_name = buildVersionedFileName(base_name, os_target_version, bitness, ext, kb)
            output_file = os.path.join(getOutputDirectory(), target_versioned_file_name)
            if os.path.exists(output_file):
                printLog(f'Skipping {target_versioned_file_name}')
                continue
            shutil.move(extracted_file, output_file)
            printSuccess(f'Extracted file {target_versioned_file_name}')
        except SymbolManagerException as ex:
            printError(f'Failed to extrapolate file! {str(ex)}')


def handleExtrapolateMsu(args):
    existing_files = '\n'.join(list(os.listdir(getOutputDirectory())))

    if args.directory:
        dir_regex = r'\.((msu)|(cab))$'
        if args.filter:
            dir_regex = args.filter[0]
        printLog(f'dir_regex: {dir_regex}')

        if not os.path.isdir(args.msu_file):
            raise argparse.ArgumentTypeError(f'msu_file must point to a directory if "-d" is passed!')
        def callback(root, msu):
            try:
                reg = re.search(r'\s+(?P<kb>(KB\d+))\s+-\s+\d+-\d+\.((msu)|(cab))$', msu, re.I)
                if reg and not args.force:
                    # Check if we have already extracted this file
                    kkk = reg.group('kb')
                    if re.search(r'jscript.*\s+' + kkk + r'.*\.dll$', existing_files, re.I | re.M):
                        printLog(f'Skipping already extracted patch file {msu}')
                        return
                extrapolateMsuFile(msu, args)
            except SymbolManagerException as ex:
                printError(f'Failed to extrapolate MSU file "{os.path.join(root, msu)}" {str(ex)}')
        # walkFiles(args.msu_file, callback, r'Windows\s+10\s+2.*\.((msu)|(cab))$')
        walkFiles(args.msu_file, callback, dir_regex)
    else:
        extrapolateMsuFile(args.msu_file, args)
