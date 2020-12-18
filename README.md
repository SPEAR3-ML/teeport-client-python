# Teeport client for Python

Teeport is an optimization platform that aims to solve the communication problems between the optimizers and the evaluators in real life. Read more about Teeport [here](https://teeport.ml/intro/).

To get the big picture of how Teeport works technically, please take a look at [this Teeport tutorial](https://github.com/SPEAR3-ML/teeport-test).

This project is the python client for Teeport. It enables the evaluate/optimize functions that are written in python to talk to the optimize/evaluate functions that are written in other languagues and/or require specific resources through the [Teeport backend service](https://github.com/SPEAR3-ML/teeport-backend).

## Install

Let's install the package in the development mode.

```bash
git clone https://github.com/SPEAR3-ML/teeport-client-python.git
cd teeport-client-python
pip install -e .
```

## Uninstall

```bash
cd teeport-client-python
python setup.py develop -u
```

## Usage

Please refer to the [API docs](https://teeport-client-python.readthedocs.io/en/latest/).
