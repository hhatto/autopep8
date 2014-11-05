all:
	@echo "make test(test_basic, test_diff, test_unit)"
	@echo "make fasttest"
	@echo "make benchmark"
	@echo "make pypireg"
	@echo "make coverage"
	@echo "make check"
	@echo "make clean"

PYTHON?=python
COVERAGE?=coverage

TEST_DIR=test
.PHONY: test
test: test_basic test_diff test_unit
fasttest: test_fast

test_basic:
	@echo '--->  Running basic test'
	@${PYTHON} autopep8.py --aggressive test/example.py > .tmp.test.py
	pep8 --repeat .tmp.test.py
	@rm .tmp.test.py

test_diff:
	@echo '--->  Running --diff test'
	@cp test/example.py .tmp.example.py
	@${PYTHON} autopep8.py --aggressive --diff .tmp.example.py > .tmp.example.py.patch
	patch < .tmp.example.py.patch
	@rm .tmp.example.py.patch
	pep8 --repeat .tmp.example.py && ${PYTHON} -m py_compile .tmp.example.py
	@rm .tmp.example.py

test_unit:
	@echo '--->  Running unit tests'
	@${PYTHON} test/test_autopep8.py

test_fast:
	@echo '[run]' > .pytest.coveragerc
	@echo 'branch = True' >> .pytest.coveragerc
	@echo 'omit = "*/site-packages/*"' >> .pytest.coveragerc
	@echo '[report]' >> .pytest.coveragerc
	@echo 'include = autopep8.py' >> .pytest.coveragerc
	@AUTOPEP8_COVERAGE=1 py.test -n4 --cov-config .pytest.coveragerc \
		--cov-report term-missing --cov autopep8 test/test_autopep8.py
	@rm .pytest.coveragerc .coverage

coverage:
	@coverage erase
	@AUTOPEP8_COVERAGE=1 ${COVERAGE} run --branch --parallel-mode --omit='*/site-packages/*' test/test_autopep8.py
	@${COVERAGE} combine
	@${COVERAGE} report --show-missing
	@${COVERAGE} xml --include=autopep8.py

open_coverage: coverage
	@${COVERAGE} html
	@python -m webbrowser -n "file://${PWD}/htmlcov/index.html"

benchmark:
	@echo '--->  Benchmark of autopep8.py test/example.py'
	@time ${PYTHON} autopep8.py --aggressive test/example.py > /dev/null
	@echo '--->  Benchmark of test_unit'
	@time ${PYTHON} test/test_autopep8.py > /dev/null
	@echo '--->  Benchmark of autopep8.py -d test/*.py'
	@time ${PYTHON} autopep8.py -d test/*.py > /dev/null

readme:
	@${PYTHON} update_readme.py
	@rstcheck README.rst
	@${PYTHON} -m doctest -v README.rst

open_readme: readme
	@python -m webbrowser -n "file://${PWD}/README.html"

check:
	pep8 autopep8.py setup.py test/acid.py test/acid_pypi.py update_readme.py
	pylint \
		--reports=no \
		--msg-template='{path}:{line}: [{msg_id}({symbol}), {obj}] {msg}' \
		--disable=bad-builtin \
		--disable=bad-continuation \
		--disable=bad-option-value \
		--disable=fixme \
		--disable=invalid-name \
		--disable=locally-disabled \
		--disable=missing-docstring \
		--disable=no-absolute-import \
		--disable=no-member \
		--disable=no-self-use \
		--disable=not-callable \
		--disable=old-division \
		--disable=protected-access \
		--disable=redefined-builtin \
		--disable=star-args \
		--disable=too-few-public-methods \
		--disable=too-many-arguments \
		--disable=too-many-branches \
		--disable=too-many-instance-attributes \
		--disable=too-many-lines \
		--disable=too-many-locals \
		--disable=too-many-public-methods \
		--disable=too-many-statements \
		--disable=undefined-loop-variable \
		--disable=unicode-builtin \
		--rcfile=/dev/null autopep8.py setup.py update_readme.py
	pylint \
		--reports=no \
		--msg-template='{path}:{line}: [{msg_id}({symbol}), {obj}] {msg}' \
		--max-module-lines=2500 \
		--disable=bad-continuation \
		--disable=basestring-builtin \
		--disable=blacklisted-name \
		--disable=duplicate-code \
		--disable=fixme \
		--disable=import-error \
		--disable=invalid-name \
		--disable=line-too-long \
		--disable=missing-docstring \
		--disable=no-absolute-import \
		--disable=no-member \
		--disable=protected-access \
		--disable=redefined-builtin \
		--disable=relative-import \
		--disable=star-args \
		--disable=too-many-arguments \
		--disable=too-many-branches \
		--disable=too-many-lines \
		--disable=too-many-public-methods \
		--rcfile=/dev/null \
		--dummy-variables-rgx='^_+$$' \
		test/acid.py test/acid_pypi.py test/test_autopep8.py
	./autopep8.py --diff autopep8.py setup.py test/test_autopep8.py update_readme.py

mutant:
	@mut.py --disable-operator RIL -t autopep8 -u test.test_autopep8 -mc

pypireg:
	${PYTHON} setup.py register
	${PYTHON} setup.py sdist upload

clean:
	rm -rf .tmp.test.py temp *.pyc *egg-info dist build \
		__pycache__ */__pycache__ */*/__pycache__ \
		htmlcov coverage.xml
