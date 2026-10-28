.PHONY: test api reports docker
test:
	python -m pytest
api:
	python -m uvicorn processlens.api:app --port 8810 --reload
reports:
	for s in samples/*.bpmn; do python -m processlens.cli "$$s" "$${s%.bpmn}.md" --out out; done
docker:
	docker build -t processlens . && docker run --rm -p 8810:8810 processlens
