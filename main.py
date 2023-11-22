#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Purpose: Microsoft Windows Symbols Manager
Author: Michael K. Steinberg
Date: 25/09/2023
"""
import argparse
import re
import sys
from typing import List
from src.patch.get_kbs import mapPatchKbsToDate
from src.patch.patch_download import downloadPatches, downloadPatchesByKb
# from patchactor import extract_patch, parse_express_psf_manifest, parse_manifests
from src.iso.iso_extractor import extractInternalSourceFiles, extractInternalSourceFilesFromDir
from src.iso.wim_extractor import extractFilesFromInstallWim, extractInternalSourceFilesFromWimDir
from src.patch.delta_patch import handleExtrapolateMsu, handleExtrapolatePatch
from src.psf.psf_extractor import extractFileFromPsf
from src.psf.psf_manifest import parsePsfExpressManifest
from src.sort.sort import sortBinaries
from src.utils.printer import printError, printInfo, printLog
from src.utils.settings import getInterestingFiles, getInterestingFilesAsRegex, getOutputDirectory, getSettings, setAllowedToDownloadPdbsMode, setDownloadSettingsAllowDynamic, setKeepTmpFilesMode, setVerboseMode
from src.utils.utils import validateFilePath, validateFilePathDir, setOutputDirectory, validateRegex, walkFiles


def parseSettingsFlags(args):
    if args.download_pdbs:
        setAllowedToDownloadPdbsMode(args.download_pdbs)
    if args.keep:
        setKeepTmpFilesMode(args.keep)
    if args.verbose:
        setVerboseMode(args.verbose)
        printLog(f'Verbose mode is on.')
    if args.out:
        setOutputDirectory(args.out, args.accept)


__g_alias_map = {
    None: None,
}
def __registerAliases(command: str, aliases: List[str]) -> List[str]:
    __g_alias_map[command] = command
    for a in aliases:
        if a in __g_alias_map.keys():
            raise Exception('Overlapping aliases found!')
        __g_alias_map[a] = command
    return aliases


def __makeAliases(command: str) -> List[str]:
    return __registerAliases(command, [command[0].lower(), command[0].upper(), command.upper(), command.capitalize()])


def handleDownload(args):
    args.download = __g_alias_map[args.download]
    if args.allow_dynamic:
        setDownloadSettingsAllowDynamic(True)
    if args.download == 'patches':
        windows_major = args.major
        windows_minor = args.minor if (args.minor.lower() != 'none') else ''
        windows_bitness = args.bitness
        downloadPatches(windows_major, windows_minor, windows_bitness, getOutputDirectory())
    elif args.download == 'kb':
        if args.major:
            windows_major = args.major
            downloadPatchesByKb(windows_major, getOutputDirectory())
        elif args.kb_number:
            downloadPatchesByKb('', getOutputDirectory(), kb_number=args.kb_number)


def handleExtract(args):
    args.extract = __g_alias_map[args.extract]
    if args.extract == 'iso':
        if args.dir:
            extractInternalSourceFilesFromDir(args.dir, getOutputDirectory(), *getInterestingFiles())
        elif args.file:
            extractInternalSourceFiles(args.file, getOutputDirectory(), *getInterestingFiles())
        else:
            raise argparse.ArgumentTypeError('Please specify either a file or directory!')
    elif args.extract == 'wim':
        if args.dir:
            extractInternalSourceFilesFromWimDir(args.dir, getOutputDirectory(), *getInterestingFiles())
        elif args.file:
            extractFilesFromInstallWim(args.file, getOutputDirectory(), *getInterestingFiles())
        else:
            raise argparse.ArgumentTypeError('Please specify either a file or directory!')
    elif args.extract == 'psf':
        extractFileFromPsf(args.psf_file_path, args.psf_xml_file_path, args.file_name_regex if args.file_name_regex else getInterestingFilesAsRegex(), getOutputDirectory())


def handleExtrapolate(args):
    args.extrapolate = __g_alias_map[args.extrapolate]
    if args.extrapolate == 'patch':
        handleExtrapolatePatch(args)
    elif args.extrapolate == 'msu':
        handleExtrapolateMsu(args)


def handleSort(args):
    args.sort = __g_alias_map[args.sort]
    if args.sort == 'bin':
        sortBinaries(args.dir, getOutputDirectory(), args.file_name_regex, args.cut, args.recursive)
    elif args.sort == 'builds':
        mapPatchKbsToDate(args.major[0])


__s_command_handlers = {
    'extract': handleExtract,
    'download': handleDownload,
    'extrapolate': handleExtrapolate,
    'sort': handleSort,
}


def main():
    try:
        options_parser = argparse.ArgumentParser(add_help=False)
        # Flags
        verbosity_group = options_parser.add_mutually_exclusive_group()
        verbosity_group.add_argument('-v', '--verbose', help="Verbose output", action='store_true')
        verbosity_group.add_argument('-vl', '--verbosity', help="Verbose output", nargs=1, metavar='level')
        options_parser.add_argument('-y', '--accept', help="Auto accept all prompts", action='store_true')
        options_parser.add_argument('-dp', '--download-pdbs', help="Allow downloading of PDBs", action='store_true')
        options_parser.add_argument('-k', '--keep', help="Keep temporary files", action='store_true')

        output_parser = argparse.ArgumentParser(add_help=False)
        output_parser.add_argument('-o', '--out', help="Output directory for extracted files")

        parser = argparse.ArgumentParser(parents=[options_parser, output_parser])

        subparsers = parser.add_subparsers(title='Commands', dest='command', description='Available commands')

        extract_command = subparsers.add_parser('extract', aliases=__registerAliases('extract', ['x', 'X', 'EXTRACT', 'Extract']), allow_abbrev=True, description='Extract files from archives', help='Extracts files from complex Microsoft archives (MSU, PSF, WIM, ESD,...)', parents=[output_parser, options_parser])
        download_command = subparsers.add_parser('download', aliases=__makeAliases('download'), allow_abbrev=True, description='Download files from Microsoft\'s servers', help='Download files from Microsoft\'s servers', parents=[output_parser, options_parser])
        extrapolate_command = subparsers.add_parser('extrapolate', aliases=__makeAliases('extrapolate'), allow_abbrev=True, description='Extrapolate binaries with patches', help='Combine base exe/dll files with patch files to extrapolate the patched binary', parents=[output_parser, options_parser])
        sort_command = subparsers.add_parser('sort', aliases=__makeAliases('sort'), allow_abbrev=True, description='Sort relevant files', help='Sorts binaries and pdbs in a scattered directory tree and renames the files correctly', parents=[output_parser, options_parser])
        
        # Extract
        extract_type = extract_command.add_subparsers(dest='extract')

        psf_group = extract_type.add_parser('psf', aliases=__registerAliases('psf', ['PSF']), description='Parse & extract PSF patch files', help='Parse & extract PSF patch files', parents=[output_parser, options_parser])
        psf_group.add_argument('psf_file_path', help="Patch PSF binary file", type=validateFilePath, metavar='psf_file_path')
        psf_group.add_argument('psf_xml_file_path', help="PSF XML file", type=validateFilePath, metavar='psf_xml_file_path')
        psf_group.add_argument('file_name_regex', help='Names of files to extract as regex', type=validateRegex, nargs='?')

        iso_group = extract_type.add_parser('iso', aliases=__registerAliases('iso', ['ISO']), description='Parse & extract image files', help='Parse & extract image files', parents=[output_parser, options_parser])
        iso_args = iso_group.add_mutually_exclusive_group()
        iso_args.add_argument('-f', '--file', help="File path for an ISO", type=validateFilePath, metavar='iso_file_path')
        iso_args.add_argument('-d', '--dir', help="Path to a directory full of ISOs", type=validateFilePathDir, metavar='isos_directory')

        wim_group = extract_type.add_parser('wim', aliases=__registerAliases('wim', ['WIM','esd','ESD']), description='Parse & extract WIM/ESD files', help='Parse & extract WIM/ESD files', parents=[output_parser, options_parser])
        wim_args = wim_group.add_mutually_exclusive_group()
        wim_args.add_argument('-f', '--file', help="File path for an install.wim", type=validateFilePath, metavar='wim_file_path')
        wim_args.add_argument('-d', '--dir', help="Path to a directory full of install.wim & install.esd files", type=validateFilePathDir, metavar='wims_directory')

        # Sort
        sort_type = sort_command.add_subparsers(dest='sort')

        binaries_group = sort_type.add_parser('bin', aliases=__registerAliases('bin', ['BIN', 'binary', 'binaries']), description='Sort binaries', help='Sort & rename binaries and correct their names with unique and acurate names (including full version)', parents=[output_parser, options_parser])
        builds_group = sort_type.add_parser('builds', aliases=__makeAliases('builds'), description='Fetch meta-data about KBs', help='Fetch meta-data about KBs', parents=[output_parser, options_parser])

        binaries_group.add_argument('dir', help="Path to a directory to sort", type=validateFilePathDir, metavar='directory_path')
        binaries_group.add_argument('-x', '--cut', help="Move files instead of copying them", action='store_true')
        binaries_group.add_argument('-r', '--recursive', help="Recursively walk the directory", action='store_true')
        binaries_group.add_argument('file_name_regex', help="Names of files to sort as regex", type=validateRegex, nargs='?')

        builds_group.add_argument('major', nargs=1)

        # Extrapolate
        extrapolate_type = extrapolate_command.add_subparsers(dest='extrapolate')

        patch_group = extrapolate_type.add_parser('patch', aliases=__makeAliases('patch'), help='Create a patched file from raw patch files (and possibly executable)', parents=[options_parser])
        msu_group = extrapolate_type.add_parser('msu', aliases=__makeAliases('msu'), help='Apply an entire update and patch coresponding files', parents=[output_parser, options_parser])

        patch_group_mode = patch_group.add_mutually_exclusive_group(required=True)
        patch_group_output = patch_group.add_mutually_exclusive_group(required=True)
        patch_group_mode.add_argument("-f", "--file",
                        help="File to patch (forward or reverse)")
        patch_group_mode.add_argument("-n", "--null", action="store_true", default=False,
                        help="Create the output file from a null diff "
                            "(null diff must be the first one specified)")
        patch_group_output.add_argument("-o", "--output-file")
        patch_group_output.add_argument("-d", "--dry-run", action="store_true",
                            help="Don't write patch, just see if it would patch"
                                "correctly and get the resulting hash")
        patch_group.add_argument("-l", "--legacy", action='store_true', default=False,
                        help="Let the API use the PA19 legacy API (if required)")
        patch_group.add_argument("patches", nargs='+', help="Patches to apply")


        msu_group.add_argument('msu_file', type=validateFilePath, help='An MSU update file from the security catalog')
        msu_group.add_argument('base_files_dir', type=validateFilePathDir, help='Root directory of base files onto which to apply the patches (not in-place)', nargs='?')
        msu_group.add_argument('-n', '--name', type=validateRegex, help='Names of files to extrapolate as regex', nargs=1, metavar='REGEX_NAME')
        msu_group.add_argument('-t', '--filter', type=validateRegex, help='File name filter - which patches to extrapolate', nargs=1, metavar='REGEX_NAME')
        msu_group.add_argument('-d', '--directory', help='Treat "msu_file" as a directory full of MSU files', action='store_true')
        msu_group.add_argument('-f', '--force', help='Skip checking if patch was already extracted', action='store_true')

        # Download
        download_type = download_command.add_subparsers(dest='download')
        download_options = argparse.ArgumentParser(add_help=False)
        download_options.add_argument('--allow-dynamic', help='Also download the "Dynamic" version of the update (preserves locales)', action='store_true')

        patches_group = download_type.add_parser('patches', aliases=__registerAliases('patches', ['PATCHES', 'Patches']), description='Download patches', help='Download patches', parents=[output_parser, options_parser, download_options])
        patches_group.add_argument('major', help="Major windows version")
        patches_group.add_argument('minor', help="Minor windows version")
        patches_group.add_argument('bitness', help="Windows bitness")

        kb_group = download_type.add_parser('kb', aliases=__registerAliases('kb', ['KB', 'Kb', 'kB']), description='Download by KBs', help='Download by kernel builds', parents=[output_parser, options_parser, download_options])
        kb_group_choice = kb_group.add_mutually_exclusive_group(required=True)
        kb_group_choice.add_argument('--major', help="Major windows version")
        kb_group_choice.add_argument('--kb_number', help="KB exact number")

        args = parser.parse_args()

        parseSettingsFlags(args)

        args.command = __g_alias_map[args.command]
        if not args.command:
            raise argparse.ArgumentTypeError('No command specified!')

        __s_command_handlers[args.command](args)

    except argparse.ArgumentTypeError as ex:
        printError(f'Argument error: {ex}')

if __name__ == "__main__":
    main()
