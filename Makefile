.PHONY: setup demo run test smoke clean

setup:
	uv venv .venv
	. .venv/bin/activate && uv pip install -e '.[dev]'

demo:
	python scripts/generate_demo_assets.py

run:
	. .venv/bin/activate && uvicorn trendcut_agent.app:app --host 127.0.0.1 --port 8765 --reload

test:
	. .venv/bin/activate && pytest tests -q

smoke: demo
	. .venv/bin/activate && python scripts/smoke_run.py

clean:
	rm -rf output data .pytest_cache backend/trendcut_agent/__pycache__ tests/__pycache__

audit:
	python scripts/public_audit.py
