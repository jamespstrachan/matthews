#!/bin/sh
# To use, copy this file into this repo's .git/hooks dir

flake8 --exclude "*/migrations/*",manage.py,"*/static/*","*/templates/*" --max-line-length=100 --ignore E221,E127,E241,E203,W504 || exit 1
