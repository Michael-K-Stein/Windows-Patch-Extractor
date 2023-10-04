"""
Purpose: PDBPE - PDB + PE
Author: Michael K. Steinbergs
Created: 29/09/2023
"""
import os
import subprocess
import pythoncom
import tqdm
from win32com.client import Dispatch
from utils import ExeBuildInfo, PeInfo, SymbolManagerException, dbh_fii, dbh_info, parse_dbh_info_as_dict, pdb_sig_70_to_str
pythoncom.CoInitialize()

ROOT_PDB_SEARCH_DIRS = [
    r'C:\symbols',
]


class PDBPE:
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
        self.m_pdb_file_path = self.extrapolate_pdb_path(pdb_file_path, [self.m_root_dir, self.m_rel_dir] + ROOT_PDB_SEARCH_DIRS)
        if not self.m_pdb_file_path:
            raise SymbolManagerException(f'No PDB found for file {pe_file_path}')
        self.m_classic_pdb_path = os.path.join(root_dir, self.m_pe_info.m_pdb_classic_path)
        self.m_is_pdb_in_classic_path = os.path.abspath(self.m_classic_pdb_path) == os.path.abspath(self.m_pdb_file_path)
        self.m_dbh_fii = dbh_fii(os.path.abspath(self.m_file_path))
        self.m_classic_pe_path = os.path.join(root_dir, self.m_dbh_fii["file"], f'{self.m_dbh_fii["timestamp"][2:].upper()}{self.m_dbh_fii["size"][2:].lower()}', self.m_dbh_fii["file"])
        self.m_file_name = self.m_dbh_fii["file"]
        self.m_is_pe_in_classic_path = os.path.abspath(self.m_classic_pe_path) == os.path.abspath(self.m_file_path)
        self.get_file_properties()

    def get_file_properties(self):
        self.m_properties = { }
        shell = Dispatch('WScript.Shell')
        original_name = shell.Exec(f"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe $file = Get-ChildItem '{self.m_file_path}'; $file.VersionInfo.InternalName").StdOut.ReadAll().strip()
        win_build_major = shell.Exec(f"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe $file = Get-ChildItem '{self.m_file_path}'; $file.VersionInfo.FileBuildPart").StdOut.ReadAll().strip()
        win_patch_num = shell.Exec(f"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe $file = Get-ChildItem '{self.m_file_path}'; $file.VersionInfo.FilePrivatePart").StdOut.ReadAll().strip()
        raw_version = shell.Exec(f"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe $file = Get-ChildItem '{self.m_file_path}'; $file.VersionInfo.FileVersionRaw.ToString()").StdOut.ReadAll().strip()
        self.m_properties['original_name'] = original_name
        self.m_properties['build'] = win_build_major
        self.m_properties['patch'] = win_patch_num
        self.m_properties['version'] = raw_version

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
