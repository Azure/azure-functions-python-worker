#!/bin/bash

set -e -x

coverage combine
coverage xml
coverage erase
