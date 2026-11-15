setup:
	cd back && python -m venv .venv && .venv/bin/pip install -r requirements.txt && cp -n .env.example .env

run:
	cd back && .venv/bin/uvicorn app.main:app --port 8000

test:
	cd back && .venv/bin/pytest -q

eval:
	cd back && .venv/bin/python -m eval.run_eval
