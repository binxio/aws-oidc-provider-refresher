import binascii
import ssl
from typing import Iterator, Tuple
from urllib.parse import urlparse

import boto3
import requests
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes

from aws_oidc_provider_refresher.logger import log
from aws_oidc_provider_refresher.schema import validate
from aws_oidc_provider_refresher.tag import Tag, TagFilter


class InvalidOpenIDEndpointException(Exception):
    def __init__(self, msg):
        super(InvalidOpenIDEndpointException, self).__init__(msg)


class Command:
    def __init__(
        self,
        max_thumbprints: int = 5,
        append: bool = True,
        verbose: bool = False,
        dry_run: bool = False,
        tags: Tuple[Tag] = [],
    ):
        self.iam = boto3.client("iam")
        self.tagging = boto3.client("resourcegroupstaggingapi", region_name="us-east-1")
        self.verbose = verbose
        self.dry_run = dry_run
        self.max_thumbprints = max_thumbprints
        self.append = append
        self.tag_filters = TagFilter(tags).to_api()

    def find_oidc_providers(self) -> Iterator[str]:
        """
        iterates over all the matching OIDC providers filtered by `self.tag_filters`,
        returning the ARN.
        """
        if self.tag_filters:
            if self.verbose:
                log.info("selecting OIDC providers with filter %s", self.tag_filters)
            get_resources = self.tagging.get_paginator("get_resources")
            for resources in get_resources.paginate(
                TagFilters=self.tag_filters,
                ResourceTypeFilters=["iam:oidc-provider"],
            ):
                for resource in resources["ResourceTagMappingList"]:
                    yield resource["ResourceARN"]
        else:
            if self.verbose:
                log.info("selecting all OIDC providers")
            response = self.iam.list_open_id_connect_providers()
            for provider in response["OpenIDConnectProviderList"]:
                yield provider["Arn"]

    @staticmethod
    def get_public_key(url: str) -> x509.Certificate:
        """
        gets the public key of an Open ID Connect provider.
        >>> c = Command.get_public_key("https://accounts.google.com")
        >>> c.issuer.rfc4514_string()
        'CN=GTS CA 1C3,O=Google Trust Services LLC,C=US'
        """
        wks = f"{url}/.well-known/openid-configuration"
        response = requests.get(wks, headers={"Accept": "application/json"})
        if response.status_code != 200:
            raise InvalidOpenIDEndpointException(
                f"expected 200 from {url}, got {response.status_code}, {response.text}"
            )

        configuration = response.json()
        if "jwks_uri" not in configuration:
            raise ValueError("%s did not return a proper openid configuration", wks)

        jwks_uri = urlparse(configuration["jwks_uri"])

        conn = None
        try:
            conn = ssl.create_connection((jwks_uri.netloc, 443))
            context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
            sock = context.wrap_socket(conn, server_hostname=jwks_uri.netloc)
            certificate = ssl.DER_cert_to_PEM_cert(sock.getpeercert(True))
            return x509.load_pem_x509_certificate(
                certificate.encode("ascii"), default_backend()
            )
        finally:
            if conn:
                conn.close()

    @staticmethod
    def fingerprint(certificate: x509.Certificate) -> str:
        """
        returns the sha1 fingerprint of the certificate, which is exactly 40 characters.
        >>> fingerprint = Command.fingerprint(Command.get_public_key("https://accounts.google.com"))
        >>> import re
        >>> match = re.fullmatch(r'[0-9a-f]{40}', fingerprint)
        >>> match and match.group() == fingerprint
        True
        """
        sha1 = certificate.fingerprint(hashes.SHA1())
        return binascii.hexlify(sha1).decode("ascii").lower()

    def update_thumbprint_list(self, provider: dict, fingerprint: str) -> bool:
        """
        appends the fingerprint to the provider's thumbprint list and returns True,
        if the list is updated. If it is already in the list, the list is unchanged
        and False is returned.
        >>> c = Command()
        >>> oidc_provider = {'Url': 'https://accounts.google.com'}
        >>> c.update_thumbprint_list(oidc_provider, 'fp1')
        True
        >>> oidc_provider['ThumbprintList']
        ['fp1']
        >>> c.update_thumbprint_list(oidc_provider, 'fp1')
        False
        >>> oidc_provider['ThumbprintList']
        ['fp1']
        >>> c.update_thumbprint_list(oidc_provider, 'fp2')
        True
        >>> oidc_provider['ThumbprintList']
        ['fp1', 'fp2']
        >>> c.max_thumbprints = 1
        >>> c.update_thumbprint_list(oidc_provider, 'fp3')
        True
        >>> oidc_provider['ThumbprintList']
        ['fp3']
        """
        thumbprints = provider.get("ThumbprintList", [])
        exists = list(filter(lambda f: f.lower() == fingerprint, thumbprints))
        if exists:
            return False

        thumbprints.append(fingerprint)
        if self.max_thumbprints and len(thumbprints) > self.max_thumbprints:
            thumbprints = thumbprints[-self.max_thumbprints :]

        provider["ThumbprintList"] = thumbprints
        return True

    def update_provider_thumbprint(self, provider: dict) -> bool:
        """
        updates the OIDC provider thumbprint list, with the fingerprint of
        the provider's public key and returns True. If the fingerprint is
        already present,the provider is unchanged and False is returned.
        A maximum of `self.max_thumbprints` is maintained in the list.

        >>> c = Command(verbose=True)
        >>> provider = {'Url': 'https://accounts.google.com'}
        >>> fp = c.fingerprint(c.get_public_key(provider['Url']))
        >>> c.update_provider_thumbprint(provider)
        True
        >>> provider['ThumbprintList'][0] == fp
        True
        """
        url = provider.get("Url")
        public_key = self.get_public_key(
            url if url.startswith("http") else f"https://{url}"
        )
        fingerprint = Command.fingerprint(public_key)
        result = self.update_thumbprint_list(provider, fingerprint)

        if result:
            if self.verbose:
                issuer = public_key.issuer.rfc4514_string()
                subject = public_key.subject.rfc4514_string()
                log.info(
                    f"new fingerprint {fingerprint} found of {url}, subject {subject} issued by {issuer}"
                )
            else:
                log.info(
                    f"new fingerprint {fingerprint} found of {url} valid until {public_key.not_valid_after}"
                )
        elif self.verbose:
            log.info(
                f"fingerprint of {url} already in thumbprint list of OIDC provider"
            )

        return result

    def run(self):
        """
        updates the thumbprint list of all selected OIDC providers
        """
        count = 0
        updated = 0
        for arn in self.find_oidc_providers():
            count = count + 1
            provider = self.iam.get_open_id_connect_provider(
                OpenIDConnectProviderArn=arn
            )
            if not self.update_provider_thumbprint(provider):
                continue

            if not self.dry_run:
                self.iam.update_open_id_connect_provider_thumbprint(
                    OpenIDConnectProviderArn=arn,
                    ThumbprintList=provider["ThumbprintList"],
                )
            updated = updated + 1
        if self.dry_run:
            log.info(
                f"Would update {updated} out of {count} OpenID connect providers, but no changes were made\n"
            )
        else:
            log.info(
                f"found {count} OpenID connect providers, {updated} of which were updated.\n"
            )


def handle(request: dict, _: dict):
    """
    AWS Lambda entrypoint.
    """
    if not validate(request):
        raise Exception("ignoring invalid request received")

    request["tags"] = tuple(map(lambda s: Tag.from_string(s), request["tags"]))
    Command(**request).run()
