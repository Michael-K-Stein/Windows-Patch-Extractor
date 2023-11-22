import shutil
import tempfile

from src.utils.settings import keepTmpFiles


class TmpDir:
    """
    A context manager for creating and managing temporary directories.

    This class creates a temporary directory when entering a 'with' block and deletes it when exiting the block.
    
    Example:
        ```python
        with TmpDir(prefix="my_prefix_", suffix="_temp") as tmp:
            # Your code here
            print(f"Working in temporary directory: {tmp}")
            # The temporary directory is automatically deleted when the 'with' block exits.
        ```

    Attributes:
        tmp_dir (str): The path to the created temporary directory.

    Methods:
        __init__(self, prefix: str = "", suffix: str = ""): Initializes the TmpDir instance with optional prefix and suffix.
        __enter__(): Enters the context and creates the temporary directory.
        __exit__(exc_type, exc_value, traceback): Exits the context and deletes the temporary directory.
    """
    def __init__(self, prefix: str = "symmgr_", suffix: str = ""):
        """
        Initialize a TmpDir instance with optional prefix and suffix for the temporary directory.

        Args:
            prefix (str, optional): A string to prepend to the temporary directory name.
            suffix (str, optional): A string to append to the temporary directory name.
        """
        self.tmp_dir = None
        self.prefix = prefix
        self.suffix = suffix

    def __enter__(self):
        """
        Create a temporary directory with the specified prefix and suffix, and return its path.

        Returns:
            str: The path to the created temporary directory.
        """
        self.tmp_dir = tempfile.mkdtemp(prefix=self.prefix, suffix=self.suffix)
        return self.tmp_dir

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Delete the temporary directory when exiting the context.

        Args:
            exc_type: The type of exception (if an exception occurred).
            exc_value: The exception instance (if an exception occurred).
            traceback: The traceback object (if an exception occurred).
        """
        if self.tmp_dir and not keepTmpFiles():
            shutil.rmtree(self.tmp_dir)
