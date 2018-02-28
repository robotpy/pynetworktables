#!/bin/bash

set -e
cd `dirname $0`

PYTHONPATH=.. python -m coverage run --source networktables,ntcore -m pytest $@
python -m coverage report -m
