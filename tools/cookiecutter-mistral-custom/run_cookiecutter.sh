#!/bin/bash

if [ ! -f "/usr/local/bin/cookiecutter" ]
then
    echo "Installing cookiecutter"
    if [[ $EUID -ne 0 ]]; then
      SUDO=sudo
    fi
    $SUDO pip install cookiecutter
fi

cookiecutter .
