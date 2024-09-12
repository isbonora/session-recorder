# session-recorder

[![PyPI](https://img.shields.io/pypi/v/session-recorder.svg)](https://pypi.org/project/session-recorder/)
[![Changelog](https://img.shields.io/github/v/release/isbonora/session-recorder?include_prereleases&label=changelog)](https://github.com/isbonora/session-recorder/releases)
[![Tests](https://github.com/isbonora/session-recorder/actions/workflows/test.yml/badge.svg)](https://github.com/isbonora/session-recorder/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/isbonora/session-recorder/blob/master/LICENSE)

Record Vicon and Logs from a QA session

## Installation

Install this tool using `pip`:
```bash
pip install session-recorder
```
## Usage

For help, run:
```bash
session-recorder --help
```
You can also use:
```bash
python -m session_recorder --help
```
## Development

To contribute to this tool, first checkout the code. Then create a new virtual environment:
```bash
cd session-recorder
python -m venv venv
source venv/bin/activate
```
Now install the dependencies and test dependencies:
```bash
pip install -e '.[test]'
```
To run the tests:
```bash
python -m pytest
```
