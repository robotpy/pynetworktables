#!/bin/bash

set -e
cd `dirname $0`

PYTHONPATH=.. python -m coverage run --source networktables -m pytest "$@"
python -m coverage report -m
