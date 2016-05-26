#!/bin/bash -xe

SCRIPT_DIR="$(dirname "$(readlink -e "${BASH_SOURCE[0]}")")"

(
    cd "$SCRIPT_DIR"

    docker build -t mistral-all -f Dockerfile ../..
)
