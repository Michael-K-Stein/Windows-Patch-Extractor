class PatchKB:
    """
    A class to represent a Windows patch.

    This class provides a way to store and manipulate information about a Windows patch. Each patch is identified by a unique 'kb' attribute, and also has 'major' and 'patch' attributes to store additional information about the patch.

    Attributes:
        kb (str): The unique identifier for the patch. Defaults to 'KB0000000'.
        major (str): The major version number of the patch. Defaults to '0000'.
        patch (str): The patch version number. Defaults to '0'.

    Methods:
        __str__(self) -> str: Returns a string representation of the patch.
        __repr__(self) -> str: Returns a string that can be used to recreate the object.
        __eq__(self, other): Checks if two PatchKB objects are equal.
        __lt__(self, other): Checks if this PatchKB object is less than another.
        __gt__(self, other): Checks if this PatchKB object is greater than another.
        __hash__(self): Returns a hash value for the object.
    """

    kb = 'KB0000000'
    major = '0000'
    patch = '0'
    year = ''
    month = ''

    def __init__(self, kb, major, patch, year = None, month = None):
        self.kb = kb
        self.major = major
        self.patch = patch
        self.year = year
        self.month = month

    def __str__(self) -> str:
        return f'Windows {self.major}.{self.patch} - {self.kb}'

    def __repr__(self) -> str:
        return f'PatchKB({self.kb}, {self.major}, {self.patch})'

    def __eq__(self, other):
        """
        Checks if two PatchKB objects are equal by comparing their 'kb', 'major', and 'patch' attributes.

        Args:
            other (PatchKB): The other PatchKB object to compare with.

        Returns:
            bool: True if the two objects are equal, False otherwise.
        """
        if not isinstance(other, PatchKB):
            return False
        return self.kb == other.kb and self.major == other.major and self.patch == other.patch

    def __lt__(self, other):
        """
        Checks if this PatchKB object is less than the other PatchKB object by comparing their 'kb' attributes.

        Args:
            other (PatchKB): The other PatchKB object to compare with.

        Returns:
            bool: True if this object is less than the other object, False otherwise.
        """
        if not isinstance(other, PatchKB):
            return False
        return int(self.kb[2:]) < int(other.kb[2:])

    def __gt__(self, other):
        """
        Checks if this PatchKB object is greater than the other PatchKB object by comparing their 'kb' attributes.

        Args:
            other (PatchKB): The other PatchKB object to compare with.

        Returns:
            bool: True if this object is greater than the other object, False otherwise.
        """
        if not isinstance(other, PatchKB):
            return False
        return int(self.kb[2:]) > int(other.kb[2:])


    def __hash__(self):
        """
        Returns a hash value for the object based on the 'kb' attribute.

        This method makes 'PatchKB' a hashable type, which means instances
        of 'PatchKB' can be used as keys in a dictionary or added to a set.

        Returns:
            int: A hash value for the object.
        """
        return hash(self.kb)
