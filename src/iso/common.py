import os
from typing import List
from src.externals.proc import ExternalProcedureException
from src.externals.z7 import z7ExtractFiles
from src.utils.printer import printError, printLog, printSuccess


def genericExtractFromArchive(archive_path: str, output_dir: str, error_message_archive_name: str, *file_names) -> List[str]:
    printLog(f'Extracting files from "{archive_path}" to "{output_dir}"')
    try:
        extracted_files = z7ExtractFiles(archive_path, output_dir, flat_output_dir=False, file_filters=file_names)
        if not extracted_files:
            printError(f'No files were extracted from the {error_message_archive_name}!')
            return []
        
        pretty_extracted_files = list(set(os.path.basename(file_name) for file_name in extracted_files))
        extracted_files_compact = ', '.join(pretty_extracted_files[:5])
        if len(extracted_files) >= 5:
            extracted_files_compact += f'... + {len(extracted_files) - len(pretty_extracted_files[:5])} more'
        if len(extracted_files) == 1:
            printSuccess(f'The following file was extracted: {extracted_files_compact}')
        else:
            printSuccess(f'The following files were extracted: {extracted_files_compact}')
        return extracted_files
    except ExternalProcedureException as ex:
        printError(f'Openning {archive_path} as archive failed!')
        return []
