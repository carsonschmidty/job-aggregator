.PHONY: ingest validate test
ingest:
	python -m scripts.ingest
validate:
	python -m scripts.validate
test:
	python -m pytest -q
