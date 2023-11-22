import re
import xml.etree.ElementTree as XML
from src.externals.proc import run
from src.utils.printer import printLog
from src.utils.settings import getOutputDirectory


def extractPatch(patch_file_path, capture_ps_output=False):
    proc = run(['Powershell', '-ExecutionPolicy', 'Bypass', '-File', 'PatchExtract.ps1', '-Patch', patch_file_path, '-Path', getOutputDirectory()], capture_output=capture_ps_output)
    return proc


def parseManifestXml(xml_file_path: str):
    try:
        with open(xml_file_path, 'r') as f:
            data = XML.parse(f)
        return set([a for a in re.findall(r'(ntoskrnl)', data, re.I)])
    except Exception as ex:
        return ex


def getTrueTag(node: XML.Element) -> str | None:
    reg = re.search(r'{(\w|\d|\\|:|\/|\.)+}(?P<tag_name>\w+)', node.tag, re.I)
    if not reg:
        return None
    return reg.group('tag_name')


def getChildByTag(parent: XML.Element, child_tag: str, *grandchild_tag) -> XML.Element | None:
    vals = [d for d in parent if getTrueTag(d).lower() == child_tag.lower()]
    if not vals:
        return None
    if not grandchild_tag:
        return vals[0]
    return getChildByTag(vals[0], *grandchild_tag)
