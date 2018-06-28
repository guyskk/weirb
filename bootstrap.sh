#! /bin/bash
set -ex

pip install -r requires-dev.txt
pip install -e .

pre-commit install
