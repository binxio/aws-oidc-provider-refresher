# AWS Open ID Connect provider thumbprint refresherer

## install
to install the utility, type:

```sh
pip install aws-oidc-provider-refresher
```

## deploy as Lambda
To deploy the refresherer as an AWS Lambda, type:

```sh
git clone https://github.com/binxio/aws-oidc-provider-refresher.git
cd aws-oidc-provider-refresher
aws cloudformation deploy \
	--capabilities CAPABILITY_IAM \
	--stack-name aws-oidc-provider-refresher \
	--template-file ./cloudformation/aws-oidc-provider-refresher.yaml
```
This will install the log minder in your AWS account and run every hour.
