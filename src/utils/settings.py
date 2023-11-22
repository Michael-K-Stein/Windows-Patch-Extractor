import re
from typing import List

# Aliases


class Settings:
    s_output_dir = 'KernelFiles'
    s_allowed_to_download_pdbs = False
    s_local_pdbs_dir = 'PDBs'
    s_keep_tmp_files = False
    s_verbose = False
    s_allowed_to_download_dynamic_updates = False

g_settings = Settings()

def getSettings() -> Settings:
    return g_settings


def isVerboseMode() -> bool:
    return getSettings().s_verbose


def setVerboseMode(mode: bool = True):
    getSettings().s_verbose = mode


def setKeepTmpFilesMode(mode: bool = True):
    getSettings().s_keep_tmp_files = mode


def keepTmpFiles() -> bool:
    return getSettings().s_keep_tmp_files


def getOutputDirectory() -> str:
    return getSettings().s_output_dir

# Set output dir is implemented in another file due to circular dependencies


def isAllowedToDownloadPdbs() -> bool:
    return getSettings().s_allowed_to_download_pdbs


def setAllowedToDownloadPdbsMode(mode: bool = True):
    getSettings().s_allowed_to_download_pdbs = mode


def isAllowedToDownloadDynamicUpdates() -> bool:
    return getSettings().s_allowed_to_download_dynamic_updates


def setDownloadSettingsAllowDynamic(mode: bool = True):
    getSettings().s_allowed_to_download_dynamic_updates = mode


def getInterestingFiles() -> List[str]:
    return [
        '*ntos*.exe', '*ntdll*.dll', '*ntos*.sys', 
        '*kernel32.dll', '*kernelbase.dll',
        '*ws2_32.dll', '*CRYPTBASE.DLL', '*dwrite.dll',
        '*dbghelp.dll', '*WINMM.dll', '*sechost.dll', '*sechost.dll',
        '*bcryptprimitives.dll', '*msvcrt.dll', '*advapi32.dll',
        '*RPCRT4.dll', '*combase.dll', '*ucrtbase.dll', 
        '*msvcp_win.dll', '*OLEAUT32.dll', 
        '*clfs.sys',

        # '*ntdll*.dll'
        ]


def getInterestingFilesAsRegex() -> re.Pattern[str]:
    return r'.*((ntos)|(ntdll)|(kernel((32)|(base)))|(ws2_32)|(dbghelp)|(WINMM)|(bcryptprimitives)|(sechost)|(msvcrt)|(advapi32)|(RPCRT4)|(combase)|(ucrtbase)|(msvcp_win)|(OLEAUT32)|(CRYPTBASE)|(clfs)).*\.((dll)|(exe)|(sys))$'


def confirm_action(message):
    while True:
        user_input = input(f"{message} (y/n): ").strip().lower()
        if user_input in ("y", "yes"):
            return True
        elif user_input in ("n", "no"):
            return False
        else:
            print("Please enter 'y' for Yes or 'n' for No.")
