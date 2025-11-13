#!/bin/sh

# shellcheck disable=SC2046
if [ $(pgrep kopf | wc -l) -lt 1 ]; then
  exit 1
else
  exit 0
fi
