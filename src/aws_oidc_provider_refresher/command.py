import boto3
import requests
import binascii
import ssl
import sys
from urllib.parse import urlparse
from typing import Iterator
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
        max_thumbprints: int = 0,
        append: bool = True,
        verbose: bool = False,
        dry_run: bool = False,
        tags: [Tag] = [],
    ):
        self.iam = boto3.client("iam")
        self.tagging = boto3.client("resourcegroupstaggingapi", region_name="us-east-1")
        self.verbose = verbose
        self.dry_run = dry_run
        self.max_thumbprints = max_thumbprints
        self.append = append
        self.tag_filters = TagFilter(tags).to_api()

    def find_oidc_providers(self) -> Iterator[str]:
        get_resources = self.tagging.get_paginator("get_resources")
        for resources in get_resources.paginate(
            TagFilters=self.tag_filters,
            ResourceTypeFilters=["iam:oidc-provider"],
        ):
            for resource in resources["ResourceTagMappingList"]:
                yield resource["ResourceARN"]

    @staticmethod
    def get_public_key(url: str):
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

    def update_provider_thumbprint(self, provider: dict) -> bool:
        url = provider.get("Url")

        public_key = self.get_public_key(
            url if url.startswith("http") else f"https://{url}"
        )
        sha1 = public_key.fingerprint(hashes.SHA1())
        fingerprint = binascii.hexlify(sha1).decode("ascii").lower()

        thumbprints = provider.get("ThumbprintList")
        exists = list(filter(lambda f: f.lower() == fingerprint, thumbprints))
        if exists:
            if self.verbose:
                log.info(
                    f"fingerprint of {url} already in thumbprint list of OIDC provider"
                )
            return False

        if self.verbose:
            subject = public_key.subject.rfc4514_string()
            issuer = public_key.issuer.rfc4514_string()
            log.info(f"new fingerprint {fingerprint} found of {url}, subject {subject} issued by {issuer}")
        else:
            log.info(
                    f"new fingerprint {fingerprint} found of {url} valid until {public_key.not_valid_after}"
            )

        if self.max_thumbprints and len(thumbprints) + 1 > self.max_thumbprints:
            thumbprints = thumbprints[1:]
            if self.verbose:
                log.info(
                    f"limiting the number of thumbprints to {self.max_thumbprints}"
                )

        if self.append:
            thumbprints.append(fingerprint)
        else:
            thumbprints = [fingerprint]

        provider["ThumbprintList"] = thumbprints
        return True

    def run(self):
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
                    OpenIDConnectProviderArn=arn, ThumbprintList=provider["ThumbprintList"],
                )
            updated = updated + 1
        if self.dry_run:
            log.info(
                f"found {count} OpenID connect providers, would update {updated}\n"
            )
        elif updated > 0:
            log.info(
                f"found {count} OpenID connect providers, {updated} of which were updated.\n"
            )


def handle(request: dict, _: dict):
    if not validate(request):
        raise Exception("ignoring invalid request received")

    request["tags"] = list(map(lambda s: Tag.from_string(s), request["tags"]))
    Command(**request).run()
