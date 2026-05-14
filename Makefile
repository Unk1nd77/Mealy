SHELL := /bin/bash

.PHONY: quality quality-backend quality-frontend

quality:
	./scripts/quality.sh

quality-backend:
	./scripts/quality.sh backend

quality-frontend:
	./scripts/quality.sh frontend
