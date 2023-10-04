"""
Purpose: Extract NT Kernel & System files from ISOs
Author: Michael K. Steinberg
Date: 30/09/2023
"""


import re
import subprocess
import uuid
import os
import tqdm
from colorama import Fore, Style
import argparse
from ppe import PDBPE

Z7_BIN_PATH = r'7z\7z.exe'
g_output_dir = ['KernelFiles']
def get_output_dir() -> str:
    return g_output_dir[0]
def set_output_dir(v) -> str:
    global g_output_dir
    g_output_dir[0] = v


def verbose_subprocess_run(params, *args, **kwargs) -> subprocess.CompletedProcess[str]:
    cmd_line_str = subprocess.list2cmdline(params)
    tqdm.tqdm.write(Style.DIM + '> ' + cmd_line_str + Style.RESET_ALL)
    return subprocess.run(params, *args, capture_output=True, **kwargs)


def print_info(s, *args, **kwargs):
    tqdm.tqdm.write('[~] ' + s, *args, **kwargs)


def print_log(s, *args, **kwargs):
    tqdm.tqdm.write(Fore.YELLOW + '[=] ' + s + Style.RESET_ALL, *args, **kwargs)


def print_success(s, *args, **kwargs):
    tqdm.tqdm.write(Fore.CYAN + '[+] ' + s + Style.RESET_ALL, *args, **kwargs)


def print_error(s, *args, **kwargs):
    tqdm.tqdm.write(Fore.RED + '[!] ' + s + Style.RESET_ALL, *args, **kwargs)


def extract_wim(iso_path: str) -> str:
    print_info(f'Extracting ISO "{iso_path}"')
    tmp_path = str(uuid.uuid4()).replace('-', '')
    os.makedirs(tmp_path, exist_ok=True)
    proc = verbose_subprocess_run([Z7_BIN_PATH, 'l', iso_path, f'-o{tmp_path}', '-bd', '-mmt', '-bb0', '-slt', r'sources\install.wim', r'sources\install.esd'])
    files = proc.stdout.decode()
    files = files[files.index('----------'):]
    file_found_re = re.search(r'path\s*=\s*(?P<file_path>(\w|\d|\\|\.)+)', files, re.I)
    if not file_found_re:
        print_error(f'Regex error!')
        os.removedirs(tmp_path)
        return ''
    fp = file_found_re.group('file_path')
    if not fp:
        print_error(f'Failed to find matching files!')
        os.removedirs(tmp_path)
        return ''
    verbose_subprocess_run([Z7_BIN_PATH, 'e', iso_path, f'-o{tmp_path}', '-bd', '-mmt', '-bb0', fp])
    path = os.path.join(tmp_path, os.path.basename(fp))
    if not os.path.exists(path):
        print_error(f'Failed to extract {fp} to {path}!')
        os.removedirs(tmp_path)
        return ''
    return path


def extract_from_wim(wim_path: str, files_wildpaths: str, output_dir: str):
    out = verbose_subprocess_run([Z7_BIN_PATH, 'x', '-r', '-mmt', '-aou', wim_path, f'-o{output_dir}'] + files_wildpaths)
    fre = re.search(r'files\s*:\s*(?P<file_count>\d+)', out.stdout.decode(), re.I)
    if not fre:
        print_error(f'Regex error!')
        return
    fc = fre.group('file_count')
    if not fc:
        print_error(f'Failed to get extracted file count!')
        return
    print_info(out.stdout.decode())
    print_success(f'Extracted {int(fc)} {str(files_wildpaths)} file(s)')


def fix_extracted_file_names(file_names):
    return 
    exe = PDBPE(root, binary_path)
    tqdm.tqdm.write(f'Binary: {binary_path}')
    base, ext = os.path.splitext(exe.m_file_name)
    bin_original_name = exe.m_properties['original_name']
    # legacy_build = get_ntos_build(root, binary_path)
    new_binary_name_base = f'{bin_original_name} - {exe.m_properties["version"]} {exe.m_pe_info.m_arch}{ext}'
    new_binary_name = os.path.join(binary_dir, new_binary_name_base)
    shutil.copy2(binary_path, new_binary_name)
    tqdm.tqdm.write(Fore.GREEN + f'Found {new_binary_name_base} !' + Style.RESET_ALL)



def walk_tree(root, current_root, search_regex, callback):
    for r, ds, fs in tqdm.tqdm(os.walk(current_root, topdown=True)):
        for f in fs:
            if re.search(search_regex, f, re.I):
                try:
                    callback(os.path.join(r, f))
                except Exception as ex:
                    print_error(f'Exception in callback for {os.path.join(r, f)}')
        for d in ds:
            walk_tree(root, os.path.join(r, d), search_regex, callback)


def extract_kernel_files(iso_path: str):
    wim_path = extract_wim(iso_path)
    if not wim_path:
        print_error(f'No WIM/ESD file found!')
        return
    extract_kernel_files_from_wim(wim_path)
    print_info(f'Deleting: {wim_path}')
    os.remove(wim_path)
    base_dir, _ = os.path.split(wim_path)
    os.removedirs(base_dir)


def extract_kernel_files_from_wim(wim_path: str):
    interesting_files = ['*ntos*.exe', '*ntdll*.dll', '*ntos*.sys']
    extract_from_wim(wim_path, interesting_files, get_output_dir())


def validate_file_path(file_path):
    if not os.path.exists(file_path):
        raise argparse.ArgumentTypeError(f"'{file_path}' does not exist!")  
    return file_path


def validate_file_path_dir(file_path):
    fp = validate_file_path(file_path)
    if not os.path.isdir(fp):
        raise argparse.ArgumentTypeError(f"'{file_path}' is not a directory!")
    return fp


def confirm_action(message):
    while True:
        user_input = input(f"{message} (y/n): ").strip().lower()
        if user_input in ("y", "yes"):
            return True
        elif user_input in ("n", "no"):
            return False
        else:
            print("Please enter 'y' for Yes or 'n' for No.")
