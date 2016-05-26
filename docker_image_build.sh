#!/bin/bash -xe

# TODO (akovi): This script is needed practically only for the CI builds.
# Should be moved to some other place

# install docker
curl -fsSL https://get.docker.com/ | sh

sudo service docker restart

sudo -E docker pull ubuntu:14.04

# build image
sudo -E tools/docker/build.sh

sudo -E docker save mistral-all | gzip > mistral-docker.tar.gz
