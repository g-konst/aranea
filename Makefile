APP_DIR := app
PROTO_DIR := $(APP_DIR)/proto
GENERATED_DIR := $(APP_DIR)/generated
APP_IMPORT := $(shell echo $(GENERATED_DIR) | sed 's/\//./g')

PYTHON := uv run python
UVICORN := uv run uvicorn

PYTHONPATH := .

.PHONY: proto
proto:
	@mkdir -p $(GENERATED_DIR)
	@for file in $(PROTO_DIR)/*.proto; do \
		$(PYTHON) -m grpc_tools.protoc -I=$(PROTO_DIR) $$file \
		  --python_out=$(GENERATED_DIR) \
		  --grpc_python_out=$(GENERATED_DIR); \
	done
	@echo "Proto files generated"

	@for file in $(GENERATED_DIR)/*_pb2_grpc.py; do \
        sed -i 's/import \([a-zA-Z0-9_]*\)_pb2 as \1__pb2/import $(APP_IMPORT).\1_pb2 as \1__pb2/g' $$file; \
	done
	@echo "Imports updated"

.PHONY: worker
worker:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(APP_DIR)/grpc/worker.py

.PHONY: server
server:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(APP_DIR)/server.py
