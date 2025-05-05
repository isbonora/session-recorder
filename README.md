# Vicon Session Recorder

[![PyPI](https://img.shields.io/pypi/v/session-recorder.svg)](https://pypi.org/project/session-recorder/)
[![Changelog](https://img.shields.io/github/v/release/isbonora/session-recorder?include_prereleases&label=changelog)](https://github.com/isbonora/session-recorder/releases)
[![Tests](https://github.com/isbonora/session-recorder/actions/workflows/test.yml/badge.svg)](https://github.com/isbonora/session-recorder/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/isbonora/session-recorder/blob/master/LICENSE)

The Vicon session recorder captures two sets of date in realtime: 1. from a ROS2 device such as [idealworks' iw.hub](https://idealworks.com/en/iw-hub-e/) using a ssh connection with the `tail -f` command. 2. [Vicon Tracker UDP stream](https://help.vicon.com/space/Tracker42/258310768/Stream+object+data+over+a+UDP+broadcast+connection) that includes object translation & rotation data. The data is then packaged in to a single file SQLite format with a simple schema that can be extracted at a later data and processed.

![image](https://github.com/user-attachments/assets/47920202-866b-4038-bb31-146a32ec4434)


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
