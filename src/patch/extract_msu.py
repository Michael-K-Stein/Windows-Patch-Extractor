from enum import Enum
import enum
import os
import re
from types import NoneType
from typing import List
from src.psf.common import getChildByTag
from src.psf.psf_extractor import extractFileFromPsf
from src.utils.printer import printError, printInfo, printLog, printSuccess
from src.utils.tmps import TmpDir
from src.externals.z7 import z7ExtractFiles, z7ListFiles
from src.externals.expand import expandExtractFiles, expandListFiles
from src.utils.utils import SymbolManagerException
from src.utils.settings import getInterestingFiles
import xml.etree.ElementTree as XML
import datetime


class MsuPayload:
    payload_hash = None
    payload_size = 0
    payload_path = ''
    payload_type = None

    def __init__(self, payload_item: XML.Element) -> NoneType:
        self.payload_hash = payload_item.get('PayloadHash')
        self.payload_size = payload_item.get('PayloadSize')
        self.payload_path = payload_item.get('Path')
        self.payload_type = payload_item.get('PayloadType')


class MsuMetadata:
    payloads: List[MsuPayload] = None
    cab: MsuPayload = None
    psf: MsuPayload = None

    def __init__(self, xml_file_path: str) -> NoneType:
        self.file_path = xml_file_path
        self.payloads = []
        self.__parseFile()
        self.__extractData()

    def __parseFile(self):
        printLog(f'Openning file: {self.file_path}')
        with open(self.file_path, 'r', encoding='UTF-8') as f:
            self.xml_data = XML.parse(f)

    def __extractData(self):
        self.root = self.xml_data.getroot()
        self.create_time = datetime.datetime.fromisoformat(
            self.root.get('CreatedDate'))
        self.patch_month = self.create_time.strftime('%b')
        self.os_base_version = self.root.get('OSVersion')
        self.os_target_version = self.root.get('TargetOSVersion')
        self.arch = self.root.get('BuildArch')
        self.feature = getChildByTag(self.root, 'Features', 'Feature')
        self.feature_type = self.feature.get('Type')
        for payload in getChildByTag(self.root, 'Packages', 'Package', 'Payload'):
            p = MsuPayload(payload)
            self.payloads.append(p)
            if p.payload_type == 'ExpressCab':
                self.cab = p
            elif p.payload_type == 'ExpressPSF':
                self.psf = p


class MsuVersion(Enum):
    Win11 = 1
    WinServer = 2
    Win10 = 3


def extractMsuWindowsLegacy(main_cab: str, file_name: re.Pattern[str], output_dir: str, silent: bool = False):
    # if len(list(expandListFiles(main_cab, ['*PSFX.cab']))) == 0:
    extracted_files = []
    is_diff_style = re.search(
        r'Windows\d+\.\d+-(?P<kb>(KB\d+))-x\d+_PSFX\.cab', main_cab, re.I) is not None
    last_kb = re.search(r'(-|_)(?P<kb>(KB\d+))(-|_)',
                        main_cab, re.I).group('kb')
    with TmpDir() as tmp_dir:
        for sub_cab in expandExtractFiles(main_cab, tmp_dir, False, ['Cab_*.cab']):
            kb = re.search(
                r'Cab_\d+_for_(?P<kb>(KB\d+))(_PSFX)?\.cab', sub_cab, re.I).group('kb')
            if last_kb and last_kb.upper() != kb.upper():
                raise SymbolManagerException(
                    f'KB sanity check failed! {last_kb} != {kb}')
            is_diff_style = is_diff_style or (
                re.search(r'_PSFX\.cab', sub_cab, re.I) is not None)
            last_kb = kb.upper()
            extracted_files += list(expandExtractFiles(sub_cab,
                                    output_dir, False, getInterestingFiles()))
    if len(extracted_files) == 0:
        extracted_files += list(expandExtractFiles(main_cab,
                                output_dir, False, getInterestingFiles()))
    return MsuVersion.WinServer if is_diff_style else MsuVersion.Win10, last_kb, extracted_files
    # else:
    #     is_diff_style = re.search(r'Windows\d+\.\d+-(?P<kb>(KB\d+))-x\d+_PSFX\.cab', main_cab, re.I) is not None
    #     kb = re.search(r'Windows\d+\.\d+-(?P<kb>(KB\d+))-x\d+(_PSFX)?\.cab', main_cab, re.I).group('kb')
    #     return MsuVersion.WinServer if is_diff_style else MsuVersion.Win10, kb, list(expandExtractFiles(main_cab, output_dir, False, getInterestingFiles()))


def extractMsuWindowsServer(msu_file_path: str, file_name: re.Pattern[str], output_dir: str, silent: bool = False):
    with TmpDir() as tmp_dir, TmpDir() as cab_tmp_dir:
        main_cabs = z7ExtractFiles(msu_file_path, tmp_dir, file_filters=[
                                   f'Windows*.*-KB*-x*.cab'])
        if len(main_cabs) != 1:
            raise SymbolManagerException(
                f'Main CAB of Windows Server patch was not extracted properly!')
        main_cab = os.path.join(tmp_dir, main_cabs[0])
        sub_cabs = z7ExtractFiles(main_cab, cab_tmp_dir, file_filters=[
                                  f'Windows*.*-KB*-x*.cab'])
        if len(sub_cabs) != 1:
            printLog(f'Sub CAB of Windows Server patch was not extracted properly!')
            printInfo(f'Attempting extraction as Windows 10 (legacy) patch...')
            return extractMsuWindowsLegacy(main_cab, file_name, output_dir, silent)
        kb_sanity1 = re.search(
            r'Windows\d+.\d+-(?P<kb>(KB\d+))-x\d+\.cab', sub_cabs[0], re.I).group('kb')
        sub_cab = os.path.join(cab_tmp_dir, sub_cabs[0])
        psf_cab2s = z7ExtractFiles(sub_cab, cab_tmp_dir, file_filters=[
                                   f'Cab_*_for_KB*_PSFX.cab'])
        if len(psf_cab2s) == 0:
            # In older versions there is only 1 layer of CABs
            printInfo(
                f'PSF CAB2 of Windows Server patch was not extracted properly!')
            # Pretend that we found it
            psf_cab2 = sub_cab
        else:
            kb_sanity2 = re.search(
                r'Cab_\d+_for_(?P<kb>(KB\d+))_PSFX\.cab', psf_cab2s[0], re.I).group('kb')
            if kb_sanity1.lower() != kb_sanity2.lower():
                raise SymbolManagerException(f'Could not verify KB number! {
                                             kb_sanity1} != {kb_sanity2}')
            files = []
            for psf_cab2 in psf_cab2s:
                psf_cab = os.path.join(cab_tmp_dir, psf_cab2)
                files += list(expandExtractFiles(psf_cab,
                              output_dir, False, getInterestingFiles()))
            return MsuVersion.WinServer, kb_sanity1, files
        return MsuVersion.WinServer, kb_sanity1, list(expandExtractFiles(psf_cab2, output_dir, False, getInterestingFiles()))


class PackageProperties:
    def __init__(self, data: dict):
        self.appliesTo = data.get("Applies To")
        build_date = data.get("Build Date")
        self.buildDate = datetime.datetime.strptime(
            build_date, "%Y/%m/%d") if (build_date and isinstance(build_date, str)) else None
        self.company = data.get("Company")
        self.fileVersion = data.get("File Version")
        self.installationType = data.get("Installation Type")
        self.installerEngine = data.get("Installer Engine")
        self.installerVersion = data.get("Installer Version")
        self.kb = 'KB' + str(int(data.get("KB Article Number")))
        self.language = data.get("Language")
        self.packageType = data.get("Package Type")
        self.processorArchitecture = data.get("Processor Architecture")
        self.productName = data.get("Product Name")
        self.supportLink = data.get("Support Link")


def parsePkgPropertiesFile(package_properties_file_path: str) -> PackageProperties:
    with open(package_properties_file_path, 'r') as f:
        raw_data = f.read()
    regex_data = re.finditer(
        r'(?P<key>(.*?))=\"(?P<value>(.*))\"', raw_data, re.M)
    if not regex_data:
        raise SymbolManagerException(f'Invalid pkProperties file!')
    data = dict()
    for d in regex_data:
        data[d.group('key')] = d.group('value')

    return PackageProperties(data)


class MsuMetadataBase:
    arch: str = ''
    build: str = ''
    date: datetime.datetime = datetime.datetime.now()
    kb: str = ''

    def __init__(self, arch, build, date, kb):
        self.arch = arch
        self.build = build
        self.date = date
        self.kb = kb


def getMsuMetadata(msu_file_path: str) -> MsuMetadataBase:
    with TmpDir() as tmp_dir:
        metadata_files = list(z7ExtractFiles(
            msu_file_path, tmp_dir, file_filters=[f'*Metadata.cab']))

        if len(metadata_files) != 1:
            package_properties_files = list(z7ExtractFiles(
                msu_file_path, tmp_dir, file_filters=[f'*pkgProperties.txt']))
            if len(package_properties_files) != 1:
                raise SymbolManagerException(
                    f'Both Metadata & pkgProperties extraction failed!')
            package_properties_file = os.path.join(
                tmp_dir, package_properties_files[0])

            properties = parsePkgPropertiesFile(package_properties_file)

            return MsuMetadataBase(properties.processorArchitecture, properties.installerVersion.split('.')[2], properties.buildDate, properties.kb)
        else:
            metadata_file = os.path.join(tmp_dir, metadata_files[0])

            lcu_metadata_files = z7ExtractFiles(
                metadata_file, tmp_dir, file_filters=[f'LCU*.xml.cab'])
            if len(lcu_metadata_files) != 1:
                raise SymbolManagerException(
                    f'LCU metadata file was not properly extracted from the MSU\'s metadata CAB!')
            lcu_metadata_file = os.path.join(tmp_dir, lcu_metadata_files[0])

            kb_reg = re.search(r'_(?P<kb>(KB\d+))\.xml\.cab$',
                               lcu_metadata_file, re.I)
            if not kb_reg:
                raise SymbolManagerException(
                    f'Failed to find KB number from {lcu_metadata_file}')
            kb = kb_reg.group('kb')

            metadata_manifests = z7ExtractFiles(
                lcu_metadata_file, tmp_dir, file_filters=[f'*.xml'])
            if len(metadata_manifests) != 1:
                raise SymbolManagerException(
                    f'Metadata manifest file was not properly extracted from the MSU\' metadata CAB\'s LCU CAB!')
            metadata_manifest = os.path.join(tmp_dir, metadata_manifests[0])

            msu_metadata = MsuMetadata(metadata_manifest)
            printInfo(
                f'Parsing MSU for updating base version {msu_metadata.os_base_version} to \
                patched version {msu_metadata.os_target_version} : ({msu_file_path})')

            return MsuMetadataBase(msu_metadata.arch, msu_metadata.os_base_version.split('.')[2], msu_metadata.create_time, kb)


def extractMsu(msu_file_path: str, file_name: re.Pattern[str], output_dir: str, silent: bool = False):
    with TmpDir() as tmp_dir, TmpDir() as cab_tmp_dir:

        metadata_files = list(expandExtractFiles(
            msu_file_path, tmp_dir, file_filters=[f'*Metadata.cab']))
        try:
            if isinstance(metadata_files, int) or len(metadata_files) != 1:
                printLog(f'Metadata file was not properly extracted from the MSU!')
                printInfo(f'Attempting extraction as Windows Server patch...')
                return extractMsuWindowsServer(msu_file_path, file_name, output_dir, silent)
        except TypeError as ex:
            printError(f'Failed to extract \
                       MSU {msu_file_path} : {metadata_files}')
            raise SymbolManagerException(
                f'Metadata file was not properly extracted from the MSU!')

        metadata_file = os.path.join(tmp_dir, metadata_files[0])

        lcu_metadata_files = z7ExtractFiles(
            metadata_file, tmp_dir, file_filters=[f'LCU*.xml.cab'])
        if len(lcu_metadata_files) != 1:
            raise SymbolManagerException(
                f'LCU metadata file was not properly extracted from the MSU\'s metadata CAB!')
        lcu_metadata_file = os.path.join(tmp_dir, lcu_metadata_files[0])

        kb_reg = re.search(r'_(?P<kb>(KB\d+))\.xml\.cab$',
                           lcu_metadata_file, re.I)
        if not kb_reg:
            raise SymbolManagerException(
                f'Failed to find KB number from {lcu_metadata_file}')
        kb = kb_reg.group('kb')

        metadata_manifests = z7ExtractFiles(
            lcu_metadata_file, tmp_dir, file_filters=[f'*.xml'])
        if len(metadata_manifests) != 1:
            raise SymbolManagerException(
                f'Metadata manifest file was not properly extracted from the MSU\' metadata CAB\'s LCU CAB!')
        metadata_manifest = os.path.join(tmp_dir, metadata_manifests[0])

        msu_metadata = MsuMetadata(metadata_manifest)
        printInfo(f'Parsing MSU for updating base version {msu_metadata.os_base_version} to patched version {
                  msu_metadata.os_target_version} : ({msu_file_path})')

        payload_files = z7ExtractFiles(msu_file_path, tmp_dir, file_filters=[
                                       payload.payload_path for payload in msu_metadata.payloads])
        if len(payload_files) != 2:
            raise SymbolManagerException(
                f'Unexpected amount of payload items found in LCU!')

        cab_file_path = os.path.join(tmp_dir, msu_metadata.cab.payload_path)
        psf_file_path = os.path.join(tmp_dir, msu_metadata.psf.payload_path)

        express_file_paths = z7ExtractFiles(
            cab_file_path, cab_tmp_dir, file_filters=['express.psf.cix.xml'])
        if len(express_file_paths) != 1:
            raise SymbolManagerException(
                f'Express PSF XML file was not properly extracted from the MSU\'s CAB file!')
        express_file_path = os.path.join(cab_tmp_dir, express_file_paths[0])

        return MsuVersion.Win11, msu_metadata, kb, extractFileFromPsf(psf_file_path, express_file_path, file_name=file_name, output_dir=output_dir, silent=silent)
