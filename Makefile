.PHONY: test bench bench-timeout leftover
PYTHON ?= python3

test:
	$(PYTHON) -m pytest tests

bench:
	$(PYTHON) -m sandbench bench --jobs 20 --concurrency 5 --workload ok

bench-timeout:
	$(PYTHON) -m sandbench bench --jobs 6 --concurrency 3 --workload timeout

leftover:
	$(PYTHON) -m sandbench leftover
