.PHONY: test bench bench-timeout bench-oom matrix leftover
PYTHON ?= python3

test:
	$(PYTHON) -m pytest tests

bench:
	$(PYTHON) -m sandbench bench --jobs 20 --concurrency 5 --workload ok

bench-timeout:
	$(PYTHON) -m sandbench bench --jobs 6 --concurrency 3 --workload timeout

bench-oom:
	$(PYTHON) -m sandbench bench --jobs 4 --concurrency 2 --workload oom

matrix:
	$(PYTHON) -m sandbench matrix --jobs 50 --concurrency 1,10,50 --workload ok

leftover:
	$(PYTHON) -m sandbench leftover
