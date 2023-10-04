#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Purpose: Microsoft Windows Symbols Manager
Author: Michael K. Steinberg
Date: 25/09/2023
"""
import os
import sys
import argparse
import tqdm
import pefile
import subprocess
import shutil
import re
from colorama import Fore, Back, Style
import filecmp
from ppe import PDBPE
from utils import DBH_BIN_PATH, ExeBuildInfo, PeInfo, SymbolManagerException, dbh_info, parse_dbh_info_as_dict
from isoactor import *


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
        tqdm.tqdm.write(f'PDB "{pdb_file_path}" does not exist!')
        # 0 is a valid minor?
        # See version 22449.000 Windows 11 21H2 RSPRERELEASE
        return None
    pe = pefile.PE(ntos_abs_path, fast_load=True)
    build_dword = pe.get_dword_at_rva(build_number_rva)
    build_minor = pe.get_dword_at_rva(qfe_number_rva)
    build_major = build_dword & 0xffff
    return ExeBuildInfo(build_major, build_minor, exe_info.m_pe_info.m_arch)
    

def search_for_binary(start_dir: str, binary_name: str | re.Pattern[str]):
    for root, dirs, files in tqdm.tqdm(os.walk(start_dir, topdown=True)):
        for d in dirs:
            search_for_binary(os.path.join(root, d), binary_name)
        for f in files:
            if re.match(binary_name, os.path.basename(f), re.I):
                yield os.path.join(root, f)


def are_pdb_files_the_same(pdb1: str, pdb2: str) -> bool:
    return dbh_info(pdb1)['PdbSig70'] == dbh_info(pdb2)['PdbSig70'] and dbh_info(pdb1)['PdbAge'] == dbh_info(pdb2)['PdbAge']


def fix_pdb_file_tree(exe: PDBPE):
    desired_path = exe.m_classic_pdb_path
    if os.path.exists(desired_path):
        if are_pdb_files_the_same(desired_path, exe.m_pdb_file_path):
            os.remove(exe.m_pdb_file_path)
            tqdm.tqdm.write(Fore.YELLOW + f'Redundant PDB file removed ({exe.m_pdb_file_path})' + Style.RESET_ALL)
            return
        else:
            tqdm.tqdm.write(Fore.RED + f'File conflict {desired_path} & {exe.m_pdb_file_path}' + Style.RESET_ALL)
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
    tqdm.tqdm.write(Fore.GREEN + f'PDB moved from {exe.m_pdb_file_path} to {os.path.relpath(desired_path, exe.m_root_dir)}' + Style.RESET_ALL)


def fix_pe_file_tree(exe: PDBPE):
    desired_path = exe.m_classic_pe_path
    if os.path.exists(desired_path):
        if filecmp.cmp(desired_path, exe.m_file_path, shallow=False):
            os.remove(exe.m_file_path)
            tqdm.tqdm.write(Fore.YELLOW + f'Redundant PE file removed ({exe.m_file_path})' + Style.RESET_ALL)
            return
        else:
            tqdm.tqdm.write(Fore.RED + f'File conflict {desired_path} & {exe.m_file_path}' + Style.RESET_ALL)
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
    tqdm.tqdm.write(Fore.GREEN + f'PE moved from {exe.m_file_path} to {os.path.relpath(desired_path, exe.m_root_dir)}' + Style.RESET_ALL)


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
        tqdm.tqdm.write(Fore.YELLOW + f'Failed to create binary file directory.' + Style.RESET_ALL)
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
            tqdm.tqdm.write(f'Binary: {binary_path}')
            base, ext = os.path.splitext(exe.m_file_name)
            bin_original_name = exe.m_properties['original_name']
            # legacy_build = get_ntos_build(root, binary_path)
            new_binary_name_base = f'{bin_original_name} - {exe.m_properties["version"]} {exe.m_pe_info.m_arch}{ext}'
            new_binary_name = os.path.join(binary_dir, new_binary_name_base)
            shutil.copy2(binary_path, new_binary_name)
            tqdm.tqdm.write(Fore.GREEN + f'Found {new_binary_name_base} !' + Style.RESET_ALL)
        except SymbolManagerException as ex:
            tqdm.tqdm.write(Fore.RED + f'Error: {str(ex)}' + Style.RESET_ALL)
        except Exception as ex:
            tqdm.tqdm.write(Fore.RED + f'Critical Error: {str(ex)}' + Style.RESET_ALL)


def main():
    parser = argparse.ArgumentParser()

    # Accept ISO file as input
    parser.add_argument('-i', "--iso", type=validate_file_path, help="Path to an ISO file")
    # Accept a directory containing ISO files as input
    parser.add_argument('-d', "--iso-dir", type=validate_file_path_dir, help="Path to a directory containing ISO files")
    # Accept a WIM file as input
    parser.add_argument('-w', "--wim", type=validate_file_path, help="Path to a WIM file")
    
    parser.add_argument('-o', '--out', help="Output directory for extracted files")

    parser.add_argument('-y', '--accept', help="Auto accept all prompts", action='store_true')

    args = parser.parse_args()

    if args.out:
        set_output_dir(args.out)
        if not os.path.exists(get_output_dir()):
            if not args.accept and not confirm_action(f'Output directory does not exist. Would you like to create it now?'):
                exit(-1)
            print_log(f'Creating directory tree {get_output_dir()}')
            os.makedirs(get_output_dir())
        if not os.path.isdir(get_output_dir()):
            print_error(f'Output directory is not a directory!')
            exit(-2)

    if args.iso_dir:
        walk_tree(args.iso_dir, args.iso_dir, r'\.iso$', extract_kernel_files)
    elif args.iso:
        extract_kernel_files(args.iso)
    elif args.wim:
        extract_kernel_files_from_wim(args.wim)

if __name__ == "__main__":
    main()
