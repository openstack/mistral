#!/bin/bash
set -e

MISTRAL_IMAGE_NAME="dp-mistral-tests"

# If DOCKER_NAMES var is empty that we are not using the DP job and
# can build mistral only once
if [[ -z "${DOCKER_NAMES// }" ]]
then
    attempt=1
else
    attempt=10
fi

for i in $(seq 1 "${attempt}")
do
    if [ "${i}" -eq 10 ]
    then
        exit 1
    else
        set +e
        docker build --network host -t "${MISTRAL_IMAGE_NAME}" . && break
        set -e
    fi
done

for NAME in ${DOCKER_NAMES}
do
    docker tag "${MISTRAL_IMAGE_NAME}" "${NAME}"
done