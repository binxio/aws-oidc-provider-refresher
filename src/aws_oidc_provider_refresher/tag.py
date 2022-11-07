import click
from typing import Optional, Tuple


class Tag(object):
    """
    a key value pair.
    >>> Tag("Name")
    Name
    >>> Tag("Name", "Value")
    Name=Value
    """

    def __init__(self, key: str, value: Optional[str] = None):
        super(Tag, self).__init__()
        self.key = key
        self.value = value

    @staticmethod
    def from_string(s: str):
        """
        Creates a tag from a string representation.
        >>> Tag.from_string("Name=Value")
        Name=Value
        >>> Tag.from_string("Name")
        Name
        >>> Tag.from_string("Name=ab=c").value
        'ab=c'
        """
        splits = s.split("=", 1)
        return Tag(key=splits[0], value=None if len(splits) == 1 else splits[1])

    def __repr__(self) -> str:
        return f"{self.key}={self.value}" if self.value else self.key

    def is_match(self, tags: [dict]) -> bool:
        """
        returns True if this tag is matched in `tags`, otherwise False

        >>> Tag.from_string("Name=123").is_match([{"Key": "Name", "Value":"123"}])
        True
        >>> Tag.from_string("Name=345").is_match([{"Key": "Name", "Value":"123"}])
        False
        >>> Tag.from_string("Name").is_match([{"Key": "Name", "Value":"123"}])
        True
        >>> Tag.from_string("backup=daily").is_match([{"Key": "Name", "Value":"123"}])
        False
        """
        for tag in tags:
            if tag.get("Key") == self.key:
                return not self.value or tag.get("Value") == self.value
        return False


class TagFilter(object):
    """
    A boto3 tag filter
    >>> TagFilter((Tag("Name"),))
    [{'Key': 'Name', 'Values': []}]
    >>> TagFilter((Tag("Name", "Value"),))
    [{'Key': 'Name', 'Values': ['Value']}]
    >>> TagFilter((Tag("Name", "Value"), Tag("Name", "Value2")))
    [{'Key': 'Name', 'Values': ['Value', 'Value2']}]
    >>> TagFilter((Tag("Name", "Value"), Tag("Name", "Value")))
    [{'Key': 'Name', 'Values': ['Value']}]
    >>> TagFilter((Tag("Name", "Value"), Tag("Name", "Value2"), Tag("Region", "eu-west-1a"), Tag("Region", "eu-west-1b")))
    [{'Key': 'Name', 'Values': ['Value', 'Value2']}, {'Key': 'Region', 'Values': ['eu-west-1a', 'eu-west-1b']}]
    """

    def __init__(self, tags: Tuple[Tag]):
        self.filter = {}
        for tag in tags:
            key = tag.key
            if not self.filter.get(key):
                self.filter[key] = []
            if tag.value:
                if tag.value not in self.filter[key]:
                    self.filter[key].append(tag.value)

    def to_api(self):
        """
        returns an array of dictionaries with `Name` and `Values` set as expected by the boto3 api.
        >>> TagFilter([Tag("Name", "Value"), Tag("Name", "Value2")]).to_api()
        [{'Key': 'Name', 'Values': ['Value', 'Value2']}]
        """
        return [{"Key": k, "Values": self.filter[k]} for k in self.filter.keys()]

    def is_match(self, tags: [dict]):
        """
        returns True if this filter matches the tags, otherwise False

        >>> filter = TagFilter((Tag("Name", "vm1"), Tag("AZ", "eu-west-1a")))
        >>> filter.is_match([{'Key': 'Name', 'Value': 'vm1'}, {'Key': 'AZ', 'Value': 'eu-west-1a'}])
        True
        >>> filter.is_match([{'Key': 'Name', 'Value': 'vm2'}, {'Key': 'AZ', 'Value': 'eu-west-1a'}])
        False
        >>> filter = TagFilter((Tag("Name"), Tag("AZ", "eu-west-1a")))
        >>> filter.is_match([{'Key': 'Name', 'Value': 'vm2'}, {'Key': 'AZ', 'Value': 'eu-west-1a'}])
        True
        """
        for key, values in self.filter.items():
            for value in values:
                tag = Tag(key, value)
                if not tag.is_match(tags):
                    return False
        return True

    def __repr__(self):
        return str(self.to_api())


class TagType(click.ParamType):
    """
    an AWS tag in the form <key>=<value> or <key>.
    """

    name = "tag"

    def convert(self, value, param, ctx):
        splits = value.split("=", 1)
        return Tag(key=splits[0], value=None if len(splits) == 1 else splits[1])
