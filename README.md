# AWS Open ID Connect provider thumbprint refresher

```
Usage: aws-oidc-provider-refresher [OPTIONS]

updates the thumbprint list of Open ID connect providers.

By default, all OIDC provider thumbprints are updated. To only update OIDC
providers which are tagged with auto-refresh=true, type:

    aws-oidc-provider-refresher --filter auto-refresh=true --force

Options:
--filter TAG                    to select providers by in the format
Name=Value.
--max-thumbprints INTEGER RANGE
to keep in the thumbprint list  [1<=x<=5]
--dry-run / --force             show what should happen or update the OIDC
providers
--verbose                       show some more detailed output
--help                          Show this message and exit.
```
## Description

The AWS Open ID Connect provider is an awesome way to grant third party identities access
to your AWS account. It is very easy to configure: you only need the domain name and
the fingerprint of the certificate of the host serving the JSON Web Keys. 

To obtain this fingerprint Amazon wrote three pages of [documentation](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc_verify-thumbprint.html),
but it is by no means a once-in-a-lifetime event. In a previous post, we described how to set the fingerprint in a [CloudFormation](https://binx.io/2022/09/05/how-to-update-the-thumbprint-for-an-openid-connect-identity-provider-in-cloudformation/) template.
However, the Open ID connect identity providers regularly
renew their certificate. This means you have to refresh the fingerprint as well. 

This utility allows you to dynamically update the fingerprints of the OIDC providers. You can
do this manually or automatically when you deploy it as an AWS lambda.

## install
to install the utility, type:

```sh
pip install aws-oidc-provider-refresher
```

## update the fingerprints
To update the fingerprints, type:
```bash
$ aws-oidc-provider-refresher --verbose
INFO: Found credentials in shared credentials file: ~/.aws/credentials
INFO: selecting all OIDC providers
INFO: new fingerprint 962828776ba4dc09a2a0a2b72ff9cd0bd8c33aee found of gitlab.com, subject CN=gitlab.com,O=Cloudflare\, Inc.,L=San Francisco,ST=California,C=US issued by CN=Cloudflare Inc ECC CA-3,O=Cloudflare\, Inc.,C=US
INFO: Would update 1 out of 1 OpenID connect providers, but no changes were made
```
As you can see the utility did not make any changes yet. To update, add `--force`:

```bash
$ aws-oidc-provider-refresher --verbose --force
INFO: Found credentials in shared credentials file: ~/.aws/credentials
INFO: selecting all OIDC providers
INFO: new fingerprint 962828776ba4dc09a2a0a2b72ff9cd0bd8c33aee found of gitlab.com, subject CN=gitlab.com,O=Cloudflare\, Inc.,L=San Francisco,ST=California,C=US issued by CN=Cloudflare Inc ECC CA-3,O=Cloudflare\, Inc.,C=US
INFO: found 1 OpenID connect providers, 1 of which were updated.
```
It is as easy as that! But, the ensure that the thumbprint list is kept up-to-date we recommend
to deploy the refresher as a lambda:

## deploy as Lambda
To deploy the refresher as an AWS Lambda, type:

```sh
git clone https://github.com/binxio/aws-oidc-provider-refresher.git
cd aws-oidc-provider-refresher
aws cloudformation deploy \
	--capabilities CAPABILITY_IAM \
	--stack-name aws-oidc-provider-refresher \
	--template-file ./cloudformation/aws-oidc-provider-refresher.yaml
```
This will install the OIDC provider refresher in your AWS account and run every hour. To invoke
it manually type:
```bash
$ aws lambda invoke --function-name aws-oidc-provider-refresher \
 --query LogResult --output text \
 --payload $(base64 <<< '{"verbose": true, "dry_run": false}') \
 --log-type Tail /dev/fd/1 | \
 base64 -d
 
 START RequestId: b7f362bf-659a-4890-9b19-790a9979439f Version: $LATEST
[INFO]  2022-09-17T07:49:01.058Z        b7f362bf-659a-4890-9b19-790a9979439f    Found credentials in environment variables.
[INFO]  2022-09-17T07:49:02.318Z        b7f362bf-659a-4890-9b19-790a9979439f    selecting all OIDC providers
[INFO]  2022-09-17T07:49:04.816Z        b7f362bf-659a-4890-9b19-790a9979439f    gitlab.com now has 2 thumbprints
[INFO]  2022-09-17T07:49:04.816Z        b7f362bf-659a-4890-9b19-790a9979439f    new fingerprint 962828776ba4dc09a2a0a2b72ff9cd0bd8c33aee found of gitlab.com, subject CN=gitlab.com,O=Cloudflare\, Inc.,L=San Francisco,ST=California,C=US issued by CN=Cloudflare Inc ECC CA-3,O=Cloudflare\, Inc.,C=US
[INFO]  2022-09-17T07:49:04.936Z        b7f362bf-659a-4890-9b19-790a9979439f    found 1 OpenID connect providers, 1 of which were updated.

END RequestId: b7f362bf-659a-4890-9b19-790a9979439f
REPORT RequestId: b7f362bf-659a-4890-9b19-790a9979439f  Duration: 4089.85 ms    Billed Duration: 4090 ms        Memory Size: 128 MB     Max Memory Used: 90 MB    Init Duration: 453.23 ms        
```
