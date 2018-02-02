#!/bin/bash

cd ../../
python -m grpc_tools.protoc \
	-I./azureworker/protos \
	--python_out=. \
	--grpc_python_out=. \
	azureworker/protos/azureworker/protos/*.proto
