import json
import os
import re
from types import NoneType
from typing import Dict
import requests
from requests import session
import urllib.parse

import tqdm
from src.patch.get_kbs import getAllKbsByMajor
from src.utils.utils import SymbolManagerException, downloadFileWithProgress
from src.utils.printer import printError, printInfo, printLog, printSuccess
from src.utils.settings import getOutputDirectory, isAllowedToDownloadDynamicUpdates, isVerboseMode, preferOldPatches


BASE_URL = 'https://www.catalog.update.microsoft.com/Search.aspx'


PROXIES = {
    'http': '127.0.0.1:8080',
    'https': '127.0.0.1:8080',
}


class PatchCatalogException(SymbolManagerException):
    pass


class CatalogPatch:
    dynamic = False
    ext = None
    major = None
    real_minor = 0

    def __init__(self, data: re.Match | None, windowsMajor: str = '') -> NoneType:
        self.download_link = None
        self.data_loaded = data is not None
        if self.data_loaded:
            self.link_id = data.group('link_id')
            self.kb = data.group('kb_id')
            self.year = data.group('patch_year')
            self.month = data.group('patch_month')
            self.major = data.group('windows_major')
            self.minor = data.group('windows_minor') if 'windows_minor' in data.groupdict() else ''
            # self.real_minor = data.group('real_minor')
            self.bitness = data.group('windows_bitness')
            self.dynamic = data.group('dynamic') if 'dynamic' in data.groupdict() else False
        
        # Microsoft are stupid and sometime write Windows 10 even though it is 11
        if windowsMajor:
            self.major = windowsMajor

    def __getDownloadDialog(self) -> str:
        req = requests.post('https://www.catalog.update.microsoft.com/DownloadDialog.aspx', data = {
            'updateIDs': json.dumps([
                self.getUpdateId()
            ])
        })
        return req.text
    
    def getUpdateId(self) -> Dict[str,str]:
        return {
                "size": 0, 
                "languages": "", 
                "uidInfo": self.link_id, 
                "updateID": self.link_id
            }

    def getDownloadLink(self, index: int = 0, downloadDialog: str = None) -> str:
        regFileName = r'downloadInformation\[' + str(index) + r"\]\.enTitle\s*=\s*'\s*(?P<patch_year>\d+)-(?P<patch_month>\d+)\s+(((?P<dynamic>(Dynamic)\s+)?Cumulative Update )|((Security|(Preview of))?\s*(\w+\s+)*((Quality\s+)?(Rollup\s+)?)\s*))?(Preview\s+)?for\s+(Microsoft )?(Windows )?(?P<windows_major>\w+)\s+(operating system,? )?(Version (?P<windows_minor>\w+) )?for (?P<windows_bitness>\w+)-based Systems \((?P<kb_id>\w+)\)\s*';"
        regFileName2 = r'downloadInformation\[' + str(index) + r"\]\.enTitle\s*=\s*'\s*(?P<file_title>(.+))\s+\((?P<kb_id>(KB\d+))\)\s*';"
        nameMatch = re.search(regFileName, downloadDialog if downloadDialog else self.__getDownloadDialog(), re.IGNORECASE | re.MULTILINE)
        if not nameMatch:
            nameMatch = re.search(regFileName2, downloadDialog if downloadDialog else self.__getDownloadDialog(), re.IGNORECASE | re.MULTILINE)
            if not nameMatch:
                raise SymbolManagerException(f'No name found!')
            else:
                self.file_title = nameMatch.group('file_title')
        else:
            self.year = nameMatch.group('patch_year')
            self.month = nameMatch.group('patch_month')
            self.dynamic = bool(nameMatch.group('dynamic'))
            if not self.major:
                self.major = nameMatch.group('windows_major')
            self.minor = nameMatch.group('windows_minor')
            self.bitness = nameMatch.group('windows_bitness')
        self.kb = nameMatch.group('kb_id')

        reg = r'downloadInformation\[' + str(index) + r"\]\.files\[0\]\.url\s*=\s*'(?P<link>(https?:\/\/catalog\.s\.download\.windowsupdate\.com\/(?P<download_prefix>\w+)\/msdownload\/update\/software\/(?P<updt>(secu|updt))\/(?P<year>\d+)\/(?P<month>\d+)\/windows(?P<major>\w+)\.(?P<real_minor>\w+)-(?P<kb>\w+)-(?P<bitness>\w+)_(?P<download_id>\w+)\.(?P<ext>(cab|msu))))';"
        self.updt = 'secu'
        match = re.search(reg, downloadDialog if downloadDialog else self.__getDownloadDialog(), re.IGNORECASE | re.MULTILINE)
        if not match:
            reg = r'downloadInformation\[' + str(index) + r"\]\.files\[0\]\.url\s*=\s*" + r"'(?P<link>(https:\/\/catalog\.sf\.dl\.delivery\.mp\.microsoft\.com\/filestreamingservice\/files\/\w+-\w+-\w+-\w+-\w+\/public\/windows(?P<major>\w+)\.(?P<real_minor>\w+)-(?P<kb>\w+)-(?P<bitness>\w+)_\w+\.(?P<ext>(msu))))'"
            match = re.search(reg, downloadDialog if downloadDialog else self.__getDownloadDialog(), re.IGNORECASE | re.MULTILINE)
            if match:
                self.download_link = match.group('link')
                self.kb = match.group('kb')
                self.bitness = match.group('bitness')
                self.ext = match.group('ext')
                reg = r"downloadInformation\[" + str(index) + r"\]\.enTitle\s*=\s*'(?P<year>\d+)-(?P<month>\w+)\s+.*\(\w+\)';"
                match = re.search(reg, downloadDialog if downloadDialog else self.__getDownloadDialog(), re.IGNORECASE | re.MULTILINE)
                self.year = match.group('year')
                self.month = match.group('month')
        else:
            printInfo('got ver 1 %s %s' % (str(self.data_loaded), str(match.group('year'))))
            self.download_prefix = match.group('download_prefix')
            self.download_link = match.group('link')
            if self.data_loaded:
                if int(match.group('year')) != int(self.year):
                    raise PatchCatalogException(f'Download link year does not match! {int(match.group("year"))} != {int(self.year)}')
                if int(match.group('month')) != int(self.month):
                    raise PatchCatalogException('Download link month does not match!')
                if match.group('major') != self.major:
                    raise PatchCatalogException('Download link major does not match!')
                if match.group('kb').lower() != self.kb.lower():
                    raise PatchCatalogException('Download link kb does not match!')
                if match.group('bitness') != self.bitness:
                    raise PatchCatalogException('Download link bitness does not match!')
            else:
                self.year = match.group('year')
                self.month = match.group('month')
                if not self.major:
                    self.major = match.group('major')
                self.real_minor = match.group('real_minor')
                self.kb = match.group('kb')
                self.bitness = match.group('bitness')
                self.ext = match.group('ext')
                self.updt = match.group('updt')
            # self.download_link = f'https://catalog.s.download.windowsupdate.com/{self.download_prefix}/msdownload/update/software/{self.updt}/{self.year}/{self.month}/windows{self.major}.0-{self.kb.lower()}-{self.bitness}_{match.group("download_id")}.{self.ext}'
        if not self.download_link:
            raise SymbolManagerException(f'Failed to find download link!')
        printLog(f'Got download link {self.download_link}')
        if not self.ext:
            self.ext = os.path.splitext(self.download_link)[1]
        return self.download_link

    def download(self, fileName: str = '') -> None:
        download_link = self.download_link if self.download_link else self.getDownloadLink()
        if isVerboseMode():
            return downloadFileWithProgress(download_link, fileName)
        else:
            req = requests.get(download_link)
            if not req.ok:
                return None
            data = req.content
            if not data:
                raise SymbolManagerException(f'Failed to download {self.getDownloadName()}')
            with open(fileName, 'wb') as f:
                f.write(data)

    def getDownloadName(self) -> str:
        if self.major == '11' and not self.minor:
            self.minor = '21H2'
        return f'Windows {self.major} {self.minor} {self.bitness} - {"Dynamic " if self.dynamic else ""}{self.kb.upper()} - {self.year}-{self.month}.{self.ext if self.ext else "cab"}'


class PatchDownloader:
    url = ''
    query = ''
    windowsMajor = ''
    windowsMinor = ''
    bitness = ''

    def __init__(self, windowsMajor: str = '', windowsMinor: str = '', bitness: str = '', prefix: str = '', query: str = ''):
        self.query = query
        if not self.query:
            if windowsMinor:
                self.query = f'{prefix}Cumulative Update for Windows {windowsMajor} Version {windowsMinor} for {bitness}-based Systems'
            else:
                self.query = f'{prefix}Cumulative Update for Windows {windowsMajor} for {bitness}-based Systems'
        self.windowsMajor = windowsMajor
        self.windowsMinor = windowsMinor
        self.bitness = bitness
        self.url = PatchDownloader.buildCatalogSearchUrl(self.query)
        printLog(f'Catalog URL: {self.url}')
        self.data = requests.get(self.url).text

    def isValidBitness(self, bitness) -> bool:
        if not self.bitness:
            return True
        if isinstance(self.bitness, str):
            return self.bitness == bitness
        return bitness in self.bitness
        
    def generatePatchDownloadUrls(self):
        reg1 = r'<a\s+id=\'\w+-\w+-\w+-\w+-\w+_link\'\s+href=\s*"javascript:void\(0\);"\s*onclick=\'goToDetails\("(?P<link_id>(\w+-\w+-\w+-\w+-\w+))"\);\'\s+class="contentTextItemSpacerNoBreakLink">\s*(?P<patch_full_name>((?P<patch_year>\d+)-(?P<patch_month>\d+)\s+(((?P<dynamic>(Dynamic)\s+)?Cumulative Update )|((Security|(Preview of ))?\*(Monthly|Only) Quality Rollup ))(Preview )?for (Microsoft )?(Windows )?(?P<windows_major>\w+) (operating system,? )?(Version (?P<windows_minor>\w+) )?for (?P<windows_bitness>\w+)-based Systems \((?P<kb_id>\w+)\)))\s*<\/a>'
        reg2 = r'<a\s+id=\'\w+-\w+-\w+-\w+-\w+_link\'\s+href=\s*"javascript:void\(0\);"\s*onclick=\'goToDetails\("(?P<link_id>(\w+-\w+-\w+-\w+-\w+))"\);\'\s+class="contentTextItemSpacerNoBreakLink">\s*(?P<patch_full_name>((?P<patch_year>\d+)-(?P<patch_month>\d+)\s+(((?P<dynamic>(Dynamic)\s+)?Cumulative Update )|((Security|(Preview of ))?\s*(Monthly|Only)?\s*Quality Rollup ))?(Preview )?for (Microsoft )?(Windows )?(?P<windows_major>\w+) (operating system,? )?(Version (?P<windows_minor>\w+) )?for (?P<windows_bitness>\w+)-based Systems \((?P<kb_id>\w+)\)))\s*<\/a>'
        reg3 = r'<a\s+id=\'\w+-\w+-\w+-\w+-\w+_link\'\s+href=\s*"javascript:void\(0\);"\s*onclick=\'goToDetails\("(?P<link_id>(\w+-\w+-\w+-\w+-\w+))"\);\'\s+class="contentTextItemSpacerNoBreakLink">\s*(?P<patch_full_name>(((?P<patch_year>\d+)-(?P<patch_month>\d+))?(\w+\s+)*Update\s+for\s+(Microsoft\s+)?Windows\s+(?P<windows_major>((\w+\s+?)|((Server\s+\d+\s+(\w+\s+)?))))(\s+operating system,?\s+)?\s*?(\s*?for\s+?(?P<windows_bitness>\w+?)-based\s+Systems\s*?)?\s+\((?P<kb_id>\w+?)\)))\s*<\/a>'
        reg4 = r'<a\s+id=\'\w+-\w+-\w+-\w+-\w+_link\'\s+href=\s*"javascript:void\(0\);"\s*onclick=\'goToDetails\("(?P<link_id>(\w+-\w+-\w+-\w+-\w+))"\);\'\s+class="contentTextItemSpacerNoBreakLink">\s*(?P<patch_full_name>(((?P<patch_year>\d+)-(?P<patch_month>\d+))?Update\s+for\s+Windows\s+(?P<windows_major>\d+)\s+(for\s+(?P<windows_bitness>(x\d\d))-based\s+Systems\s+)?\((?P<kb_id>(KB\d+))\)))\s*<\/a>'
        # 	Security Monthly Quality Rollup for Windows 7 for x64-based Systems (KB5021291)
        # reg_loose = r'<a\s+id=\'\w+-\w+-\w+-\w+-\w+_link\'\s+href=\s*"javascript:void\(0\);"\s*onclick=\'goToDetails\("(?P<link_id>(\w+-\w+-\w+-\w+-\w+))"\);\'\s+class="contentTextItemSpacerNoBreakLink">\s*(?P<patch_year>\d+)-(?P<patch_month>\d+)\s+(?P<dynamic>(Dynamic)\s+)?Cumulative Update (Preview )?for (Microsoft )?Windows (?P<windows_major>\w+) (Version (?P<windows_minor>\w+) )?for (?P<windows_bitness>\w+)-based Systems \((?P<kb_id>\w+)\)\s*<\/a>'
        # reg2 = r'<a\s+id=\'\w+-\w+-\w+-\w+-\w+_link\'\s+href=\s*"javascript:void\(0\);"\s*onclick=\'goToDetails\("(?P<link_id>(\w+-\w+-\w+-\w+-\w+))"\);\'\s+class="contentTextItemSpacerNoBreakLink">\s*(?P<patch_year>\d+)-(?P<patch_month>\d+)\s+(?P<dynamic>(Dynamic)\s+)?Cumulative Update (Preview )?for Windows (?P<windows_major>\w+) for (?P<windows_bitness>\w+)-based Systems \((?P<kb_id>\w+)\)\s*<\/a>'
        for reg in (reg1, reg2, reg3, reg4, ):
            for link in re.finditer(reg, self.data, re.IGNORECASE | re.MULTILINE):
                patch_full_name = link.group('patch_full_name')
                if 'dynamic' in link.groups():
                    if not isAllowedToDownloadDynamicUpdates() and link.group('dynamic'):
                        printLog(f'Skipping "{patch_full_name}" (see --allow-dynamic)')
                        continue
                printInfo(f'Parsing catalog entry "{patch_full_name}"')
                catalogPatch = CatalogPatch(link, windowsMajor=self.windowsMajor)
                printInfo(str(catalogPatch.link_id))
                if self.isValidBitness(catalogPatch.bitness):
                    yield catalogPatch

    def bulkDownload(self, outputDirectory: str):
        catalogs = self.generatePatchDownloadUrls()
        update_ids = []
        kbs: Dict[str, CatalogPatch] = { }
        for catalog in catalogs:
            update_id = catalog.getUpdateId()
            printLog(f"Found update id {update_id['updateID']} for {catalog.getDownloadName()}")
            update_ids.append(update_id)
            kbs[catalog.kb.lower()] = catalog
            
        for index, update_id in enumerate(update_ids):
            req = requests.post('https://www.catalog.update.microsoft.com/DownloadDialog.aspx', data = {
                'updateIDs': json.dumps([update_id])
            } ) # , proxies=PROXIES, verify=False
            try:
                catalog = CatalogPatch(None)
                catalog.getDownloadLink(index, req.text)
                catalog.minor = kbs[catalog.kb.lower()].minor
                if kbs[catalog.kb.lower()].year:
                    catalog.year = kbs[catalog.kb.lower()].year
                if kbs[catalog.kb.lower()].month:
                    catalog.month = kbs[catalog.kb.lower()].month
                if str(catalog.major) == '6' and str(catalog.real_minor) == '1':
                    catalog.major = '7'
                if str(catalog.major) == '6' and str(catalog.real_minor) == '2':
                    catalog.major = '8'
                if str(catalog.major) == '6' and str(catalog.real_minor) == '3':
                    catalog.major = '8.1'
                if os.path.exists(os.path.join(outputDirectory, catalog.getDownloadName())):
                    continue
                downloadedPatchName = os.path.join(outputDirectory, catalog.getDownloadName())
                catalog.download(downloadedPatchName)
                printSuccess(f'Downloaded patch {catalog.getDownloadName()}')
            except Exception as ex:
                printError(f'Failed on {str(ex)}')

    @staticmethod
    def buildCatalogSearchUrl(query: str) -> str:
        return f'{BASE_URL}?q={urllib.parse.quote(query)}'


def downloadPatches(major: str, minor: str, bitness: str, outputDirectory: str):
    for year in range(2012, 2024):
        for month in range(1, 13):
            patch_downloader = PatchDownloader(major, minor, bitness, prefix=f'{year}-{str(month).zfill(2)} ')
            patch_downloader.bulkDownload(outputDirectory)


def bootlegDownloadKB(kb: str) -> None:
    query_url = f'{BASE_URL}?q={urllib.parse.quote(kb)}'
    with requests.session() as session:
        data = session.get(query_url).text
        # regex = r'\<a\s+id=\'(?P<download_link_id>(\w+-\w+-\w+-\w+-\w+))_link\'\s*href=\s*\"javascript:void\(0\);\"\s+onclick=\'goToDetails\(\"\w+-\w+-\w+-\w+-\w+\"\);\'\+class=\"\w+\"\>.*\s*(?P<year>)-(?P<month>)\s+(Preview\s+)?(of\s+)?(Quality\s+)?(Rollup\s+)?for\s+(?P<windows_full_name>((Windows)\s+((7)|(8)|(8\.1)|(Server\s+\d+\s+\w+))))\s+for\s+(?P<bitness>(x\d+))-based\s+systems\s+\((?P<kb>(KB\d+))\)\<\/a\>'
        regex = r'\<a\s+id=\'(?P<download_link_id>(\w+-\w+-\w+-\w+-\w+))_link\'\s*href=\s*\"javascript:void\(0\);\"\s+onclick=\'goToDetails\(\"\w+-\w+-\w+-\w+-\w+\"\);\'\s+class=\"\w+\"\>\s*(?P<full_name>((?P<year>\d+)-(?P<month>\d+)\s+(Preview\s+)?(Security\s+)?((Monthly)?\s+)?(of\s+)?(Quality\s+)?(Rollup\s+)?(\w+\s+)*(for\s+)(\w+\s+)*(?P<windows_full_name>((Windows)\s+((7)|(8)|(8\.1)|(10)|(11)|(Server\s+\d+\s+\w+)))).*\s+for\s+(?P<bitness>(x\d+))-based\s+systems\s+\((?P<spec_kb>(KB\d+))\)))\s*\<\/a\>'
        reg = re.finditer(regex, data, re.I | re.M | re.DOTALL | re.S)
        if not reg:
            raise SymbolManagerException(f'Regex pattern did not match!')
        for r in reg:
            full_name = r.group("full_name")
            windows_full_name = r.group('windows_full_name')
            bitness = r.group('bitness')
            spec_kb = r.group('spec_kb')
            year = r.group('year')
            month = r.group('month')
            printLog(f'Parsing patch entry "{full_name}"')
            link_id = r.group('download_link_id')
            data_for_download = {
                    "size": 0, 
                    "languages": "", 
                    "uidInfo": link_id, 
                    "updateID": link_id
                }
            req = requests.post('https://www.catalog.update.microsoft.com/DownloadDialog.aspx', data = { 'updateIDs': json.dumps([ data_for_download ]) }).text
            regex = r'downloadInformation\[0\]\.files\[0\]\.url\s*=\s*(\'|\")(?P<link>(https?:\/\/catalog\.\w+\.download\.windowsupdate\.com\/\w+\/msdownload\/(\w+\/)+\d+\/\d+\/windows\d+\.\d+-kb\d+-x\d+_\w+\.(?P<ext>(msu|cab))))(\'|\")'
            download_reg = re.search(regex, req, re.I)
            if not download_reg:
                continue

            ext = download_reg.group('ext')
            download_name = f'{windows_full_name} {bitness} - {spec_kb.upper()} - {year}-{month}.{ext}'
            output_file = os.path.join(getOutputDirectory(), download_name)

            if os.path.exists(output_file):
                printLog(f'Skipping downloaded file {download_name}')
                continue

            download_link = download_reg.group('link')

            if isVerboseMode():
                printLog(f'Downloading {download_name}')
                downloadFileWithProgress(download_link, output_file)
            else:
                with open(output_file, 'wb') as f:
                    f.write(session.get(download_link).content)
            printSuccess(f'Succesfully downloaded {download_name}')



def downloadPatchesByKb(major: str, outputDirectory: str, kb_number: str = ''):
    if kb_number:
        try:
            bootlegDownloadKB(kb_number)
            patch_downloader = PatchDownloader(query=kb_number)
            patch_downloader.bulkDownload(outputDirectory)
        except SymbolManagerException as ex:
            printError(f'PatchDownloader failed on {kb_number}: {ex}')
    else:
        raw_kbs = getAllKbsByMajor(major)
        kbs = list(raw_kbs)
        kbs = sorted(kbs, key=lambda x: x.kb, reverse=not preferOldPatches())
        for kb in tqdm.tqdm(kbs):
            try:
                # if major in ['7', '8', '8.1']:
                #     bootlegDownloadKB(kb.kb)
                #     continue
                patch_downloader = PatchDownloader(query=kb.kb, bitness=['x64', 'x86'], windowsMajor=major)
                patch_downloader.bulkDownload(outputDirectory)
            except SymbolManagerException as ex:
                printError(f'PatchDownloader failed on {kb.kb}: {ex}')
                continue
