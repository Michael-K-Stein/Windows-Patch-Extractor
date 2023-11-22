import gzip
import json
import requests
import os

import tqdm


def getWinBinDexVersions(file_name: str) -> dict:
    a = f'https://m417z.com/winbindex-data-insider/by_filename_compressed/{file_name}.json.gz'
    # a = f'https://winbindex.m417z.com/data/by_filename_compressed/{file_name}.json.gz'
    return json.loads(gzip.decompress(requests.get(a).content))

def generateFileName(info: dict) -> str:
    x = info['windowsVersions']
    x = x[list(x.keys())[0]]
    kb = list(x.keys())[0]
    x = x[kb]
    assm = x['assemblies']
    assm = assm[list(assm.keys())[0]]
    name = assm['attributes'][0]['name']
    assm = assm[list(assm.keys())[0]]
    updateInfo = x['updateInfo']
    base, ext = os.path.splitext(name)
    return f'{base} - {assm["version"]} {assm["processorArchitecture"]}{ext}'


def generateDownloadUrl(info: dict) -> str:
    fi = info['fileInfo']
    hs = hex(fi['timestamp'])[2:].upper() + hex(fi['virtualSize'])[2:].lower()
    a = info['windowsVersions']
    a = a[list(a.keys())[0]]
    a = a[list(a.keys())[0]]
    a = a['assemblies']
    a = a[list(a.keys())[0]]
    a = a['attributes'][0]
    name = a['name']
    return f'https://msdl.microsoft.com/download/symbols/{name}/{hs}/{name}'


def isWinBinDexFileBase(info: dict) -> bool:
    a = info['windowsVersions']
    a = a[list(a.keys())[0]]
    a = a[list(a.keys())[0]]
    assm = a['assemblies']
    assm = assm[list(assm.keys())[0]]
    if assm['assemblyIdentity']['processorArchitecture'] == 'arm64' or assm['assemblyIdentity']['processorArchitecture'] == 'arm64.arm' or assm['assemblyIdentity']['processorArchitecture'] == 'arm64.x86':
        return False
    ver = assm['assemblyIdentity']["version"]
    maj = int(ver.split('.')[2])
    if maj != 20348:
        return False
    maj = int(ver.split('.')[3])
    return maj == 1


if __name__ == '__main__':
    for file_name in tqdm.tqdm((
            # 'ntoskrnl.exe', 'ntdll.dll', 'ntosext.sys', 
             'kernel32.dll', # 'kernelbase.dll',
            # 'ws2_32.dll', 'CRYPTBASE.DLL', 'dwrite.dll',
            # 'dbghelp.dll', 'WINMM.dll', 'sechost.dll', 'sechost.dll',
            # 'bcryptprimitives.dll', 'msvcrt.dll', 'advapi32.dll',
            # 'RPCRT4.dll', 'combase.dll', 'ucrtbase.dll', 
            # 'msvcp_win.dll', 'oleaut32.dll', 
            )):
        file_name = file_name.lower()
        vers = getWinBinDexVersions(file_name)
        for v in tqdm.tqdm(vers):
            ver = vers[v]
            if not isWinBinDexFileBase(ver):
                continue
            ver_file_name = generateFileName(ver)
            out_path = os.path.join(r'C:\Users\mkupe\Downloads\KernelFiles\WinBinDex\BaseFiles', ver_file_name)
            if os.path.exists(out_path):
                tqdm.tqdm.write(f'Skipping file {ver_file_name}')
                continue
            dl = generateDownloadUrl(ver)
            tqdm.tqdm.write(f'Found file {ver_file_name} : {dl}')
            with open(out_path, 'wb') as f:
                f.write(requests.get(dl).content)
