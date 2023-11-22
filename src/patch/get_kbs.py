import json
import os
import re
from types import NoneType
from typing import Dict, List, Set
import requests
from requests import session
import urllib.parse
from src.patch.common import PatchKB
from src.utils.utils import SymbolManagerException, monthToNumber
from src.utils.printer import printError, printLog, printSuccess

WindowsVersionHistoryLink = str

class WindowsVersionHistoryLinks:
    WINDOWS_11 : WindowsVersionHistoryLink = 'https://support.microsoft.com/en-us/topic/windows-11-version-22h2-update-history-ec4229c3-9c5f-4e75-9d6d-9025ab70fcce'
    WINDOWS_10 : WindowsVersionHistoryLink = 'https://support.microsoft.com/en-us/topic/windows-10-update-history-24ea91f4-36e7-d8fd-0ddb-d79d9d0cdbda'
    WINDOWS_8 : WindowsVersionHistoryLink = 'https://support.microsoft.com/en-au/topic/windows-8-1-and-windows-server-2012-r2-update-history-47d81dd2-6804-b6ae-4112-20089467c7a6'
    WINDOWS_7 : WindowsVersionHistoryLink = 'https://support.microsoft.com/en-us/topic/windows-7-sp1-and-windows-server-2008-r2-sp1-update-history-720c2590-fd58-26ba-16cc-6d8f3b547599'

    LOOKUP_BY_MAJOR = {
        '11': WINDOWS_11,
        '10': WINDOWS_10,
        '8': WINDOWS_8,
        '7': WINDOWS_7,
    }


def getAllKbs(versionHistoryLink: WindowsVersionHistoryLink) -> Set[PatchKB]:
    req = requests.get(versionHistoryLink)
    if not req.ok:
        raise SymbolManagerException(f'Failed to query WindowsVersionHistoryLink {versionHistoryLink} !')
    content = req.text

    reg = re.compile(r'<a\s+class="supLeftNavLink"\s+data-bi-slot="\d+"\s+href="\/en-us\/help\/\d+">\w+\s+\d+,\s+\d+(&#x\d+)?;(?P<kb>(KB\d+))\s+\(OS\s+Build\s+(?P<major>\d+)\.(?P<patch>\d+)\)(\s+.*)?<\/a>', re.IGNORECASE | re.UNICODE | re.MULTILINE)
    matches = reg.finditer(content)

    kbs : Set[PatchKB] = set()
    for match in matches:
        maj = match.group('major')
        pat = match.group('patch')
        kbs.add(PatchKB(match.group('kb'), maj, pat))

    old_reg = re.compile(r'(?P<kb>(KB\d+))', re.IGNORECASE | re.UNICODE | re.MULTILINE)
    old_patches = old_reg.finditer(content)
    for match in old_patches:
        kbs.add(PatchKB(match.group('kb'), '', ''))
        
    return set(kbs)


def getAllKbsByMajor(major: str) -> Set[PatchKB]:
    versionLink = WindowsVersionHistoryLinks.LOOKUP_BY_MAJOR[major]
    return getAllKbs(versionLink)


def mapPatchKbsToDate(major: str):
    printLog(f'Major: {major}')
    versionLink = WindowsVersionHistoryLinks.LOOKUP_BY_MAJOR[major]
    data = requests.get(versionLink).text
    reg = re.finditer(r'\<a\s+class="\w+"\s+data-bi-slot="\d+"\s+href="\/\w+-\w+\/help\/(?=(\d+))\d+"\>(?P<month>\w+)\s+\d+,\s+(?P<year>\d+).*(?P<kb>(KB\w+))\s+\(OS\s+Builds?\s+', data, re.I | re.M)

    version_map = { }

    for v in reg:
        kb = v.group('kb')
        year = v.group('year')
        month = str(monthToNumber(v.group('month'))).zfill(2)
        version_map[kb] = (year, month)
        # printLog(f'{kb} {year}-{month}')

    printLog(f'version_map: {version_map}')
