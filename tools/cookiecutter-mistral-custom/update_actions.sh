#!/bin/bash

config_file=${$1:-'/etc/mistral/conf'}
mistral-db-manage --config-file $config_file populate_actions