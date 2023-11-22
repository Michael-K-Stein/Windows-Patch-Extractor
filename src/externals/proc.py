import subprocess
from colorama import Style
import tqdm
from src.utils.settings import isVerboseMode
from src.utils.utils import SymbolManagerException


class ExternalProcedureException(SymbolManagerException):
    pass


def run(params, *args, **kwargs) -> subprocess.CompletedProcess[str]:
    if isVerboseMode():
        cmd_line_str = subprocess.list2cmdline(params)
        tqdm.tqdm.write(Style.DIM + '> ' + cmd_line_str + Style.RESET_ALL)
    if 'capture_output' not in kwargs:
        kwargs['capture_output'] = True
    proc = subprocess.run(params, *args, **kwargs)
    if proc.returncode != 0:
        raise ExternalProcedureException(f'External procedure returned {proc.returncode}')
    return proc