"""
Purpose: Extract NT Kernel & System files from ISOs
Author: Michael K. Steinberg
Date: 30/09/2023
"""


import filecmp
import re
import shutil
import subprocess
import uuid
import os
import tqdm
from colorama import Fore, Style
import argparse
from src.utils.smart_exe import PDBPE
from utils import Z7_BIN_PATH, SymbolManagerException, calculate_file_hash, generate_tmp_dir, get_output_dir, get_settings, print_error, printInfo, printLog, printSuccess, verbose_subprocess_run


def extract_wim(iso_path: str) -> str:
    printInfo(f'Extracting ISO "{iso_path}"')
    tmp_path = generate_tmp_dir()
    proc = verbose_subprocess_run([Z7_BIN_PATH, 'l', iso_path, f'-o{tmp_path}', '-bd', '-mmt', '-bb0', '-slt', r'sources\install.wim', r'sources\install.esd'])
    files = proc.stdout.decode()
    files = files[files.index('----------'):]
    file_found_re = re.search(r'path\s*=\s*(?P<file_path>(\w|\d|\\|\.)+)', files, re.I)
    if not file_found_re:
        print_error(f'Regex error!')
        if not get_settings().m_keep_tmp_files:
            os.removedirs(tmp_path)
        return ''
    fp = file_found_re.group('file_path')
    if not fp:
        print_error(f'Failed to find matching files!')
        if not get_settings().m_keep_tmp_files:
            os.removedirs(tmp_path)
        return ''
    verbose_subprocess_run([Z7_BIN_PATH, 'e', iso_path, f'-o{tmp_path}', '-bd', '-mmt', '-bb0', fp])
    path = os.path.join(tmp_path, os.path.basename(fp))
    if not os.path.exists(path):
        print_error(f'Failed to extract {fp} to {path}!')
        if not get_settings().m_keep_tmp_files:
            os.removedirs(tmp_path)
        return ''
    return path


def extract_from_wim(wim_path: str, files_wildpaths: str, output_dir: str):
    tmp_path = generate_tmp_dir()
    out = verbose_subprocess_run([Z7_BIN_PATH, 'e', '-r', '-mmt', '-aou', wim_path, f'-o{tmp_path}'] + files_wildpaths)
    fre = re.search(r'files\s*:\s*(?P<file_count>\d+)', out.stdout.decode(), re.I)
    if not fre:
        print_error(f'Regex error!')
        return
    fc = fre.group('file_count')
    if not fc:
        print_error(f'Failed to get extracted file count!')
        return
    printSuccess(f'Extracted {int(fc)} {str(files_wildpaths)} file(s)')

    for root, dirs, files in os.walk(tmp_path):
        for f in files:
            try:
                fix_extracted_file_name(output_dir, root, os.path.join(tmp_path, f))
                if not get_settings().m_keep_tmp_files:
                    os.remove(os.path.join(tmp_path, f))
            except SymbolManagerException as ex:
                print_error(f'Error fixing file name: {str(ex)}')

    if not get_settings().m_keep_tmp_files:
        shutil.rmtree(tmp_path)
        try:
            os.removedirs(tmp_path)
        except Exception:
            pass


g_passed_files = set()
def fix_extracted_file_name(output_dir, root, binary_path):
    hash = calculate_file_hash(binary_path)
    if hash in g_passed_files:
        printLog(f'Skipping redundant binary {binary_path}')
        return
    g_passed_files.add(hash)
    exe = PDBPE(root, binary_path)
    printInfo(f'Binary: {binary_path}')
    base, ext = os.path.splitext(exe.m_file_name)
    bin_original_name = exe.m_properties['original_name']
    # legacy_build = get_ntos_build(root, binary_path)
    new_binary_name_base = f'{bin_original_name} - {exe.m_properties["version"]} {exe.m_pe_info.m_arch}{ext}'
    new_binary_name = os.path.join(output_dir, new_binary_name_base)
    if os.path.exists(new_binary_name):
        if filecmp.cmp(new_binary_name, exe.m_file_path, shallow=False):
            printLog(f'Skipping redundant binary {new_binary_name}')
            return
        else:
            raise SymbolManagerException(f'Binary file conflict for {new_binary_name} & {exe.m_file_path}')
    shutil.copy2(binary_path, new_binary_name)
    printSuccess(f'Found {new_binary_name_base} !')


def walk_tree(root, current_root, search_regex, callback):
    for r, ds, fs in os.walk(current_root, topdown=True):
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
    if not get_settings().m_keep_tmp_files:
        printInfo(f'Deleting: {wim_path}')
        os.remove(wim_path)
        base_dir, _ = os.path.split(wim_path)
        os.removedirs(base_dir)


def extract_kernel_files_from_wim(wim_path: str):
    interesting_files = ['*ntos*.exe', '*ntdll*.dll', '*ntos*.sys']
    extract_from_wim(wim_path, interesting_files, get_output_dir())












def open_pe_file(file_path: str):
    pe = pefile.PE(file_path, fast_load=True)
    return pe


def get_name_value_rva_from_pdb(root_search_path: str, pdb_file_path: str, symbol_name: str) -> int:
    abs_path = os.path.join(root_search_path, pdb_file_path)
    if not os.path.exists(abs_path):
        raise SymbolManagerException(f'No PDB available at "{pdb_file_path}"')
    ntos_build_number = subprocess.run(
        [DBH_BIN_PATH, pdb_file_path, 'name', symbol_name], 
        cwd=root_search_path, capture_output=True
        )
    name_info = parse_dbh_info_as_dict(ntos_build_number.stdout.decode())
    assert( name_info['name'] == symbol_name )
    rva = name_info['addr']
    modbase = name_info['modbase']
    # We want the RVA not relative to the mod base
    va = int(rva, 16) - int(modbase, 16)
    return va


def get_ntos_build(root_search_path: str, ntos_file_path: str) -> ExeBuildInfo:
    ntos_abs_path = os.path.join(root_search_path, ntos_file_path)
    exe_info = PDBPE(root_search_path, ntos_file_path)
    pdb_file_path = os.path.join(root_search_path, exe_info.m_pdb_file_path)
    try:
        build_number_rva = get_name_value_rva_from_pdb(root_search_path, pdb_file_path, 'NtBuildNumber')
        qfe_number_rva = get_name_value_rva_from_pdb(root_search_path, pdb_file_path, 'NtBuildQfe')
    except SymbolManagerException:
        # Probs means that we are missing this PDB
        print_error(f'PDB "{pdb_file_path}" does not exist!')
        # 0 is a valid minor?
        # See version 22449.000 Windows 11 21H2 RSPRERELEASE
        return None
    pe = pefile.PE(ntos_abs_path, fast_load=True)
    build_dword = pe.get_dword_at_rva(build_number_rva)
    build_minor = pe.get_dword_at_rva(qfe_number_rva)
    build_major = build_dword & 0xffff
    return ExeBuildInfo(build_major, build_minor, exe_info.m_pe_info.m_arch)
    

def search_for_binary(start_dir: str, binary_name: str | re.Pattern[str]):
    for root, dirs, files in os.walk(start_dir, topdown=True):
        for d in dirs:
            search_for_binary(os.path.join(root, d), binary_name)
        for f in files:
            if re.match(binary_name, os.path.basename(f), re.I):
                yield os.path.join(root, f)


def are_pdb_files_the_same(pdb1: str, pdb2: str) -> bool:
    return filecmp.cmp(pdb1, pdb2, shallow=False)


def fix_pdb_file_tree(exe: PDBPE):
    desired_path = exe.m_classic_pdb_path
    if os.path.exists(desired_path):
        if are_pdb_files_the_same(desired_path, exe.m_pdb_file_path):
            os.remove(exe.m_pdb_file_path)
            printLog(f'Redundant PDB file removed ({exe.m_pdb_file_path})')
            return
        else:
            raise SymbolManagerException(f'File conflict {desired_path} & {exe.m_pdb_file_path}')
    dir_tree, base_name = os.path.split(os.path.relpath(desired_path, exe.m_root_dir))
    # Make sure there is no flat file here
    facto_dir_tree = dir_tree
    is_temp_dir = os.path.exists(base_name) and os.path.isfile(base_name)
    if is_temp_dir:
        facto_dir_tree = os.path.join('_tmp', dir_tree)
    os.makedirs(facto_dir_tree, exist_ok=True)
    shutil.move(exe.m_pdb_file_path, os.path.join(facto_dir_tree, base_name))
    if is_temp_dir:
        shutil.move(facto_dir_tree, dir_tree)
    printSuccess(f'PDB moved from {exe.m_pdb_file_path} to {os.path.relpath(desired_path, exe.m_root_dir)}')


def fix_pe_file_tree(exe: PDBPE):
    desired_path = exe.m_classic_pe_path
    if os.path.exists(desired_path):
        if filecmp.cmp(desired_path, exe.m_file_path, shallow=False):
            os.remove(exe.m_file_path)
            printLog(f'Redundant PE file removed ({exe.m_file_path})')
            return
        else:
            print_error(f'File conflict {desired_path} & {exe.m_file_path}')
            return
    dir_tree, base_name = os.path.split(os.path.relpath(desired_path, exe.m_root_dir))
    # Make sure there is no flat file here
    facto_dir_tree = dir_tree
    is_temp_dir = os.path.exists(base_name) and os.path.isfile(base_name)
    if is_temp_dir:
        facto_dir_tree = os.path.join('_tmp', dir_tree)
    os.makedirs(facto_dir_tree, exist_ok=True)
    shutil.move(exe.m_file_path, os.path.join(facto_dir_tree, base_name))
    if is_temp_dir:
        shutil.move(facto_dir_tree, dir_tree)
    printSuccess(f'PE moved from {exe.m_file_path} to {os.path.relpath(desired_path, exe.m_root_dir)}')


def main_old():
    root = r'C:\Users\mkupe\Downloads\FOR_BIDUL_24-09'
    # root = r'C:\Users\mkupe\Code'
    os.chdir(root)
    # binary_name = r'(.*\.(dll|exe|sys))$'
    binary_name = r'.*ntdll.*dll$'
    try:
        binary_source_name, binary_ext = os.path.splitext(binary_name)
        binary_dir = os.path.join(root, 'ntdll')
        os.makedirs(binary_dir, exist_ok=True)
    except Exception:
        printInfo(f'Failed to create binary file directory.')
    for binary_path in search_for_binary(root, binary_name):
        # try:
        #     exe = PDBPE(root, binary_path)
        #     if not exe.m_is_pdb_in_classic_path:
        #         # File needs to be moved
        #         fix_pdb_file_tree(exe)
        #     if not exe.m_is_pe_in_classic_path:
        #         fix_pe_file_tree(exe)
        # except SymbolManagerException as ex:
        #     tqdm.tqdm.write(Fore.RED + f'Error: {str(ex)}' + Style.RESET_ALL)
        # except Exception as ex:
        #     tqdm.tqdm.write(Fore.RED + f'Critical Error: {str(ex)}' + Style.RESET_ALL)
        try:
            exe = PDBPE(root, binary_path)
            printLog(f'Binary: {binary_path}')
            base, ext = os.path.splitext(exe.m_file_name)
            bin_original_name = exe.m_properties['original_name']
            # legacy_build = get_ntos_build(root, binary_path)
            new_binary_name_base = f'{bin_original_name} - {exe.m_properties["version"]} {exe.m_pe_info.m_arch}{ext}'
            new_binary_name = os.path.join(binary_dir, new_binary_name_base)
            shutil.copy2(binary_path, new_binary_name)
            printSuccess(f'Found {new_binary_name_base} !')
        except SymbolManagerException as ex:
            print_error(f'Error: {str(ex)}')
        except Exception as ex:
            print_error(f'Critical Error: {str(ex)}')
