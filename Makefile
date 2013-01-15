all:
	@echo "make test(test_basic, test_diff, test_unit)"
	@echo "make pypireg"
	@echo "make coverage"
	@echo "make check"
	@echo "make clean"

PYTHON?=python
COVERAGE?=coverage

TEST_DIR=test
.PHONY: test
test: test_basic test_diff test_unit

test_basic:
	@echo '--->  Running basic test'
	${PYTHON} autopep8.py test/example.py > .tmp.test.py
	pep8 --repeat .tmp.test.py
	@rm .tmp.test.py

test_diff:
	@echo '--->  Running --diff test'
	@cp test/example.py .tmp.example.py
	${PYTHON} autopep8.py --diff .tmp.example.py > .tmp.example.py.patch
	patch < .tmp.example.py.patch
	@rm .tmp.example.py.patch
	pep8 --repeat .tmp.example.py && ${PYTHON} -m py_compile .tmp.example.py
	@rm .tmp.example.py

test_unit:
	@echo '--->  Running unit tests'
	${PYTHON} test/test_autopep8.py

coverage:
	@rm -rf htmlcov
	@AUTOPEP8_COVERAGE=1 ${COVERAGE} run --branch --parallel test/test_autopep8.py
	@${COVERAGE} combine
	@${COVERAGE} report
	@${COVERAGE} html
	@${COVERAGE} xml --include=autopep8.py
	@echo 'Coverage report: htmlcov/index.html'
	@rm .coverage

open_coverage: coverage
	@python -m webbrowser -n "file://${PWD}/htmlcov/index.html"

readme:
	${PYTHON} update_readme.py
	@python setup.py --long-description | rst2html --strict > README.html

open_readme: readme
	@python -m webbrowser -n "file://${PWD}/README.html"

check:
	pep8 autopep8.py
	pylint --reports=no --include-ids=yes --max-module-lines=2500 \
		--disable=C0111,C0103,E1123,F0401,R0902,R0903,W0404,W0622,R0914,R0912,R0915,R0904,R0911,R0913,W0142,E1101,E0702 \
		--rcfile=/dev/null autopep8.py
	./autopep8.py --diff test/test_autopep8.py
	./autopep8.py --diff autopep8.py

pypireg:
	${PYTHON} setup.py register
	${PYTHON} setup.py sdist upload

clean:
	rm -rf .tmp.test.py temp *.pyc *egg-info dist build \
		__pycache__ */__pycache__ */*/__pycache__ \
		htmlcov coverage.xml
