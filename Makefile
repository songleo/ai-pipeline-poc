.PHONY: preflight bootstrap build deploy demo smoke test clean

preflight:
	bash scripts/preflight.sh

bootstrap:
	bash scripts/create-cluster.sh
	bash scripts/install-argo.sh

build:
	bash scripts/build-images.sh

deploy:
	bash scripts/deploy-demo.sh

demo:
	bash scripts/port-forward.sh

smoke:
	bash scripts/smoke-test.sh

test:
	cd backend && PYTHONPATH=.:.deps python3 -m pytest
	docker build --provenance=false --target test --build-arg "NPM_REGISTRY=$${NPM_REGISTRY:-https://registry.npmmirror.com}" -t ssli-demo-frontend-test:0.1.0 frontend

clean:
	bash scripts/cleanup.sh
