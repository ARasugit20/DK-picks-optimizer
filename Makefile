.PHONY: install test lint validate smoke market-smoke api dashboard compose-up compose-down

install:
	pip install -r requirements.txt

test:
	pytest --cov=. --cov-fail-under=80

lint:
	ruff check .

validate:
	python3 -m dk_picks.cli validate-config --path betting_system/config.yaml

smoke:
	pytest tests/pipeline/test_run_market_pipeline_smoke.py tests/optimizer/ tests/test_config_validation.py -v

market-smoke:
	PYTHONPATH=. python3 -m betting_system.pipeline.run_market_pipeline --fixture

api:
	uvicorn betting_system.api.main:app --reload

dashboard:
	streamlit run streamlit_app.py

compose-up:
	docker compose up --build

compose-down:
	docker compose down
