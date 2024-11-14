"""
Purpose: PDBPE - PDB + PE
Author: Michael K. Steinbergs
Created: 29/09/2023
"""
import sys
import os
import re
import pythoncom
from win32com.client import Dispatch
from src.externals.proc import run
from src.utils.printer import printLog
from src.utils.utils import SymbolManagerException, normalizeDirtyBitness
pythoncom.CoInitialize()

DUMPBIN_PATH = os.path.join(os.path.split(sys.argv[0])[0], r'external\dumpbin\dumpbin.exe')

ROOT_PDB_SEARCH_DIRS = [
    r'C:\symbols',
]

class FileProperties:
    original_name = ''
    win_build_major = ''
    win_patch_num = ''
    raw_version = ''

def getFileProperties(file_path: str, version_only:bool = False) -> FileProperties:
    properties = FileProperties()
    shell = Dispatch('WScript.Shell')
    if not version_only:
        properties.original_name = shell.Exec(f"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe $file = Get-ChildItem '{file_path}'; $file.VersionInfo.InternalName").StdOut.ReadAll().strip()
        properties.win_build_major = shell.Exec(f"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe $file = Get-ChildItem '{file_path}'; $file.VersionInfo.FileBuildPart").StdOut.ReadAll().strip()
        properties.win_patch_num = shell.Exec(f"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe $file = Get-ChildItem '{file_path}'; $file.VersionInfo.FilePrivatePart").StdOut.ReadAll().strip()
    properties.raw_version = shell.Exec(f"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe $file = Get-ChildItem '{file_path}'; $file.VersionInfo.FileVersionRaw.ToString()").StdOut.ReadAll().strip()
    return properties

class BinaryFileData:
    bitness = 'x00'

def dumpBinaryFileData(file_path: str) -> BinaryFileData:
    proc = run([DUMPBIN_PATH, '/HEADERS', file_path])
    output = proc.stdout.decode()
    reg = re.search(r'machine \((?P<bitness>(x(\d|\w)+))\)', output)
    if not reg:
        raise SymbolManagerException(f'Failed to find bitness of file {file_path}')
    
    data = BinaryFileData()
    data.bitness = reg.group('bitness')
    return data


class SmartExe:
    m_file_path = ''
    m_pdb_file_path = ''
    m_pe_info = None
    m_root_dir = ''
    m_rel_dir = ''
    m_file_name = ''

    def __init__(self, root_dir, pe_file_path: str, pdb_file_path: str = None):
        self.m_file_path = pe_file_path
        self.m_root_dir = root_dir
        self.m_rel_dir, _ = os.path.split(pe_file_path)
        self.get_info_for_pe()
        if not pdb_file_path:
            pdb_file_path = self.m_pe_info.m_pdb_name
        self.m_pdb_file_path = self.extrapolate_pdb_path(pdb_file_path, [self.m_root_dir, self.m_rel_dir, os.path.abspath(get_settings().m_local_pdbs_dir)] + ROOT_PDB_SEARCH_DIRS)
        if not self.m_pdb_file_path:
            if not get_settings().m_allowed_to_download_pdbs:
                raise SymbolManagerException(f'No PDB found for file {pe_file_path}')
            env_sym_path = os.environ.get('_NT_SYMBOL_PATH')
            sym_path = f'SRV*{os.path.abspath(os.path.join("./", get_settings().m_local_pdbs_dir))}*{REMOTE_PDB_STORE}'
            if env_sym_path:
                sym_path += ';' + env_sym_path
            out = verbose_subprocess_run([SYMCHK_PATH, os.path.abspath(self.m_file_path), '/s', sym_path, '/oc', os.path.abspath(get_settings().m_local_pdbs_dir)])
            if 0 != out.returncode:
                print_error(f'Failed to download PDB for {self.m_file_path}')
                raise SymbolManagerException(f'Failed to download PDB for file {pe_file_path}')
        self.m_pdb_file_path = self.extrapolate_pdb_path(pdb_file_path, [self.m_root_dir, self.m_rel_dir, os.path.abspath(get_settings().m_local_pdbs_dir)] + ROOT_PDB_SEARCH_DIRS)
        if not self.m_pdb_file_path:
            raise SymbolManagerException(f'No PDB found for {self.m_file_path} even after downloading it!')
        self.m_classic_pdb_path = os.path.join(root_dir, self.m_pe_info.m_pdb_classic_path)
        self.m_is_pdb_in_classic_path = os.path.abspath(self.m_classic_pdb_path) == os.path.abspath(self.m_pdb_file_path)
        self.m_dbh_fii = dbh_fii(os.path.abspath(self.m_file_path))
        self.m_classic_pe_path = os.path.join(root_dir, self.m_dbh_fii["file"], f'{self.m_dbh_fii["timestamp"][2:].upper()}{self.m_dbh_fii["size"][2:].lower()}', self.m_dbh_fii["file"])
        self.m_file_name = self.m_dbh_fii["file"]
        self.m_is_pe_in_classic_path = os.path.abspath(self.m_classic_pe_path) == os.path.abspath(self.m_file_path)
        self.get_file_properties()

    def get_file_properties(self):
        self.m_properties = { }
        properties = getFileProperties(self.m_file_path)
        self.m_properties['original_name'] = properties.original_name
        self.m_properties['build'] = properties.win_build_major
        self.m_properties['patch'] = properties.win_patch_num
        self.m_properties['version'] = properties.raw_version

    def get_info_for_pe(self):
        self.m_pe_info = PeInfo(dbh_info(self.m_file_path))

    def extrapolate_pdb_path(self, pdb_path_guess: str, root_pdb_search_dirs: list[str]) -> str | None:
        for root_pdb_dir in root_pdb_search_dirs:
            guess = self.extrapolate_pdb_path_internal(os.path.join(root_pdb_dir, pdb_path_guess))
            if guess and self.validate_pdb_file(guess):
                return guess
        return None

    def extrapolate_pdb_path_internal(self, pdb_path_guess: str) -> str | None:
        root, ext = os.path.splitext(pdb_path_guess)
        # If this is not a '.pdb' path, add the extension and try again
        if ext.lower() != f'{os.path.extsep}pdb':
            return self.extrapolate_pdb_path_internal(f'{root}{os.path.extsep}pdb')
        if os.path.exists(pdb_path_guess):
            if os.path.isfile(pdb_path_guess):
                return pdb_path_guess
            elif os.path.isdir(pdb_path_guess):
                # Either the directory is flat, or it uses the pdb signatures (classic representation)
                pdb_sig = f'{self.m_pe_info.m_pdb_sig_70}{self.m_pe_info.m_pdb_age}'
                if os.path.exists(os.path.join(pdb_path_guess, pdb_sig)):
                    if os.path.isfile(os.path.join(pdb_path_guess, pdb_sig)):
                        # Odd, but maybe the dir looks like "./ntkrnlmp.pdb/ff123abc", being 'ff123abc' is the pdb file (and the signature)
                        return os.path.join(pdb_path_guess, pdb_sig)
                    elif os.path.isdir(os.path.join(pdb_path_guess, pdb_sig)):
                        # Classical structure
                        if os.path.exists(os.path.join(pdb_path_guess, pdb_sig, self.m_pe_info.m_pdb_name)):
                            return os.path.join(pdb_path_guess, pdb_sig, self.m_pe_info.m_pdb_name)
        return None

    def validate_pdb_file(self, pdb_file_path: str) -> bool:
        pdb_info = dbh_info(pdb_file_path)
        signature = pdb_sig_70_to_str(pdb_info['PdbSig70'])
        age = int(pdb_info['PdbAge'], 16)
        return (signature == self.m_pe_info.m_pdb_sig_70) and (age == self.m_pe_info.m_pdb_age)


def buildVersionedFileName(file_base_name: str, raw_version: str, architecture: str, file_extension: str, kb: str = None) -> str:
    architecture = normalizeDirtyBitness(architecture)
    if file_base_name == 'ntkrnlmp':
        file_base_name = 'ntoskrnl'
    if not kb:
        return f'{file_base_name} - {raw_version} {architecture}{file_extension}'
    else:
        return f'{file_base_name} - {raw_version} {architecture} - {kb}{file_extension}'


def getBinaryFileNameWithVersion(binary_file_path: str) -> str:
    properties = getFileProperties(binary_file_path, version_only=False)

    bin_original_name = binary_file_path
    # Legacy, uses the real file name (from factory, like ntkrnlmp.exe)
    if re.match(r'.*(\/|\\)\w+\.blob', binary_file_path, re.I):
        if properties.original_name and re.match(r'^\w+\.\w+$', properties.original_name.strip()):
            bin_original_name = properties.original_name
        else:
            bin_original_name = binary_file_path
    
    ext = os.path.splitext(bin_original_name)[1]
    bin_original_name = os.path.splitext(os.path.basename(bin_original_name))[0].split()[0].split('_')[0]
    file_data = dumpBinaryFileData(binary_file_path)
    arch = file_data.bitness
    arch = normalizeDirtyBitness(arch)
    return buildVersionedFileName(bin_original_name, properties.raw_version, arch, ext)
