#!/bin/bash

python -m grpc_tools.protoc \
	-I./azure/worker/protos \
	--python_out=. \
	--grpc_python_out=. \
	azure/worker/protos/azure/worker/protos/*.proto
