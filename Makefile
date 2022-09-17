include Makefile.mk

NAME=aws-oidc-provider-refresher
AWS_REGION=eu-central-1
S3_BUCKET_PREFIX=binxio-public
S3_BUCKET=$(S3_BUCKET_PREFIX)-$(AWS_REGION)

ALL_REGIONS=$(shell aws --region $(AWS_REGION) \
		ec2 describe-regions 		\
		--query 'join(`\n`, Regions[?RegionName != `$(AWS_REGION)`].RegionName)' \
		--output text)

.DEFAULT_GOAL:=help
.PHONY: help
help:		## Display this help
	$(info build and deploy $(NAME))
	awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z0-9_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

deploy: target/$(NAME)-$(VERSION).zip ## code zip to the bucket in the default region
	aws s3 --region $(AWS_REGION) \
		cp --acl \
		public-read target/$(NAME)-$(VERSION).zip \
		s3://$(S3_BUCKET)/lambdas/$(NAME)-$(VERSION).zip
	aws s3 --region $(AWS_REGION) \
		cp --acl public-read \
		s3://$(S3_BUCKET)/lambdas/$(NAME)-$(VERSION).zip \
		s3://$(S3_BUCKET)/lambdas/$(NAME)-latest.zip


deploy-all-regions: deploy		## lambda to all regions with bucket prefix
	@for REGION in $(ALL_REGIONS); do \
		echo "copying to region $$REGION.." ; \
		aws s3 --region $$REGION \
			cp --acl public-read \
			s3://$(S3_BUCKET_PREFIX)-$(AWS_REGION)/lambdas/$(NAME)-$(VERSION).zip \
			s3://$(S3_BUCKET_PREFIX)-$$REGION/lambdas/$(NAME)-$(VERSION).zip; \
		aws s3 --region $$REGION \
			cp  --acl public-read \
			s3://$(S3_BUCKET_PREFIX)-$$REGION/lambdas/$(NAME)-$(VERSION).zip \
			s3://$(S3_BUCKET_PREFIX)-$$REGION/lambdas/$(NAME)-latest.zip; \
	done

deploy-lambda: target/$(NAME)-$(VERSION).zip ## lambda to the default AWS account
	sed -i '' -e 's/lambdas\/aws-oidc-provider-refresher.*\.zip/lambdas\/aws-oidc-provider-refresher-$(VERSION).zip/g' cloudformation/aws-oidc-provider-refresher.yaml
	aws cloudformation deploy \
		--capabilities CAPABILITY_IAM \
		--stack-name $(NAME) \
		--template-file ./cloudformation/aws-oidc-provider-refresher.yaml

delete-lambda:		## from the default AWS account
	aws cloudformation delete-stack --stack-name $(NAME)
	aws cloudformation wait stack-delete-complete  --stack-name $(NAME)

demo:				## to the default AWS account
	aws cloudformation deploy --stack-name $(NAME)-demo --template cloudformation/demo.yaml --no-fail-on-empty-changeset

delete-demo:		## from the default AWS account
	aws cloudformation delete-stack --stack-name $(NAME)-demo
	aws cloudformation wait stack-delete-complete --stack-name $(NAME)-demo

deploy-pipeline:	## to the default AWS account
	aws cloudformation deploy \
	--capabilities CAPABILITY_IAM \
	--stack-name $(NAME)-pipeline \
	--template cloudformation/cicd-pipeline.yaml \
	--no-fail-on-empty-changeset

do-push: deploy

do-build: Pipfile.lock target/$(NAME)-$(VERSION).zip

upload-dist: Pipfile.lock  ## upload the distribution to pypi.org
	pipenv run twine upload dist/*

target/$(NAME)-$(VERSION).zip: setup.py src/*/*.py requirements.txt Dockerfile.lambda
	mkdir -p target
	rm -rf dist/* target/*
	pipenv run python setup.py check
	pipenv run python setup.py build
	pipenv run python setup.py sdist
	docker build --build-arg ZIPFILE=$(NAME)-$(VERSION).zip -t $(NAME)-lambda:$(VERSION) -f Dockerfile.lambda . && \
		ID=$$(docker create $(NAME)-lambda:$(VERSION) /bin/true) && \
		docker export $$ID | (cd target && tar -xvf - $(NAME)-$(VERSION).zip) && \
		docker rm -f $$ID && \
		chmod ugo+r target/$(NAME)-$(VERSION).zip

Pipfile.lock: Pipfile setup.py
	pipenv update -d

clean: ## clean the workspace
	rm -rf venv target
	find . -name \*.pyc | xargs rm 

test: Pipfile.lock	## runs the test
	for i in $$PWD/cloudformation/*; do \
		aws cloudformation validate-template --template-body file://$$i > /dev/null || exit 1; \
	done
	[ -z "$(shell ls -1 tests/test*.py 2>/dev/null)" ] || PYTHONPATH=$(PWD)/src pipenv run python3 -munittest ./tests/test*.py

fmt:  ## format all python code
	black $(shell find src -name \*.py) tests/*.py


deploy-all-regions-and-upload-dist: deploy-all-regions upload-dist
