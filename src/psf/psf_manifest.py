import os
import re
from typing import Any, Generator
import xml.etree.ElementTree as XML
import hashlib
import tqdm
from src.psf.common import getChildByTag, getTrueTag, parseManifestXml
from src.utils.printer import printInfo, printLog, printSuccess
from src.utils.settings import isVerboseMode
from src.utils.utils import SymbolManagerException


class PsfManifest:
    pass


class PsfExpressManifestTag:
    file_name = None
    delta = None
    source = None
    diff_type = None
    offset = None
    length = None
    real_file_name = None
    patch_direction = None

    def __init__(self, file_element: XML.Element) -> None:
        self.file_name = file_element.get('name')
        self.delta = getChildByTag(file_element, 'delta')
        self.source = getChildByTag(self.delta, 'source')
        self.diff_type = self.source.get('type')
        self.offset = int(self.source.get('offset'))
        self.length = int(self.source.get('length'))
        self.hash_alg = getChildByTag(self.source, 'Hash').get('alg')
        self.hash_value = getChildByTag(self.source, 'Hash').get('value')
        self.hasher = hashlib.new(self.hash_alg)

        self.real_file_name = os.path.basename(self.file_name)
        self.patch_direction = os.path.split(os.path.split(self.file_name)[0])[1]
        # printLog(f'Found "{self.real_file_name}" in PSF Express Manifest (type = {self.patch_type})')


class PsfExpressManifest(PsfManifest):
    tags = None
    xml_data = None
    patch_name = ''

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.tags = []
        self.__parseFile()
        self.__parseFilesTag()
    
    def getPatchName(self) -> str:
        return self.patch_name

    def __parseFile(self):
        printLog(f'Openning file: {self.file_path}')
        with open(self.file_path, 'r', encoding='UTF-8') as f:
            self.xml_data = XML.parse(f)
    
    def __parseFilesTag(self):
        files_tag = self.__findFilesTag()
        printLog(f'Extracting file tags from PSF Express')
        for file_tag in tqdm.tqdm(files_tag, unit='tag', disable=not isVerboseMode()):
            self.tags.append(PsfExpressManifestTag(file_tag))

    def __findFilesTag(self) -> XML.Element:
        patch = self.xml_data.getroot()
        reg = re.search(r'(?P<patch_name>\w+)-\w+.*\.\w+', patch.get('name'))
        if not reg:
            raise SymbolManagerException(f'Failed to parse patch\'s name!')
        self.patch_name = reg.group('patch_name')
        return getChildByTag(patch, 'Files')
    
    def __iter__(self) -> Generator[PsfExpressManifestTag, Any, Any]:
        for tag in self.tags:
            yield tag


def parsePsfExpressManifest(manifest_file: str, silent: bool = False) -> PsfExpressManifest:
    manifest = PsfExpressManifest(manifest_file)
    if not silent:
        printSuccess(f'Parsed manifest for patch "{manifest.getPatchName()}"')
    return manifest


def parse_manifests(manifests_dir: str):
    for root, dirs, files in os.walk(manifests_dir):
        for f in files:
            path = os.path.abspath(os.path.join(root, f))
            if os.path.splitext(path)[1].lower() != '.xml':
                continue
            xml = parseManifestXml(path)
            if xml:
                print(path, xml)
