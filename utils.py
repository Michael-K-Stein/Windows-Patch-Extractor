import os
import subprocess

DBH_BIN_PATH = r'C:\Program Files (x86)\Windows Kits\10\Debuggers\x64\dbh.exe'


def pdb_sig_70_to_str(pdb_sig: str) -> str:
    return ''.join(x.strip()[2:] for x in pdb_sig.split(','))


def parse_dbh_info_as_dict(dbh_info: str) -> dict[str, str]:
    info = dbh_info.splitlines()
    data = { }
    for line in info:
        vals = line.split(':', maxsplit=1)
        key = vals[0]
        key = key.strip()
        value = None
        # Some values may be null
        assert( len(vals) <= 2 )
        if len(vals) == 2:
            value = vals[1]
            value = value.strip()
        data[key] = value
    return data


def dbh_info(file_path: str) -> dict[str, str]:
    dbh_info = subprocess.run([DBH_BIN_PATH, file_path, 'info'], capture_output=True)
    return parse_dbh_info_as_dict(dbh_info.stdout.decode())


def dbh_fii(file_path: str) -> dict[str, str]:
    dbh_fii = subprocess.run([DBH_BIN_PATH, 'fii', file_path], capture_output=True)
    return parse_dbh_info_as_dict(dbh_fii.stdout.decode())


class SymbolManagerException(Exception):
    pass


class ExeBuildInfo:
    ARCH_LOCALE_MAP = {
        'X64': 'x64',
        'I386': 'x86'
    }
    def __init__(self, major, minor, arch):
        self.m_major = major
        self.m_minor = minor
        self.m_arch = self.ARCH_LOCALE_MAP[arch.upper()]


class PeInfo:
    ARCH_LOCALE_MAP = {
        'X64': 'x64',
        'I386': 'x86'
    }
    def __init__(self, pe_info: dict):
        self.m_pdb_name = pe_info['CVData']
        self.m_pdb_sig_70 = pdb_sig_70_to_str(pe_info['PdbSig70'])
        self.m_pdb_age = int(pe_info['PdbAge'], 16)
        self.m_pdb_classic_path = os.path.join(self.m_pdb_name, f'{self.m_pdb_sig_70}{self.m_pdb_age}', self.m_pdb_name)
        self.m_arch = self.ARCH_LOCALE_MAP[pe_info['MachineType']]
