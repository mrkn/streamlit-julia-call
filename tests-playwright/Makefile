PYTEST = poetry run pytest

.PHONY: tests-playwright
tests-playwright:
	@rm -rf ./test-results
	$(PYTEST) --browser chromium --screenshot only-on-failure --output ./test-results/ -r aR -v -s
