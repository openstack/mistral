#!/bin/bash
set -e

CLOUD_FLOW_IMAGE_NAME="postgres-proxy"

docker build --network host -t "${CLOUD_FLOW_IMAGE_NAME}" .

for NAME in ${DOCKER_NAMES}
do
    docker tag "${CLOUD_FLOW_IMAGE_NAME}" "${NAME}"
done
