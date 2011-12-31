all:
	@echo "make test(test_basic, test_diff, test_unit)"
	@echo "make pypireg"
	@echo "make coverage"
	@echo "make check"
	@echo "make clean"


TEST_DIR=test
.PHONY: test test_basic test_diff test_unit
test: test_basic test_diff test_unit

test_basic:
	@echo '--->  Running basic test'
	python autopep8.py test_target.py > .tmp.test.py
	pep8 -r .tmp.test.py && echo 'OK'
	@rm .tmp.test.py

test_diff:
	@echo '--->  Running --diff test'
	@cp test_target.py .tmp.test_target.py
	python autopep8.py --diff .tmp.test_target.py > .tmp.test_target.py.patch
	patch < .tmp.test_target.py.patch
	@rm .tmp.test_target.py.patch
	pep8 -r .tmp.test_target.py && echo 'OK'
	@rm .tmp.test_target.py

test_unit:
	@echo '--->  Running unit tests'
	python test/test_autopep8.py

coverage:
	@rm -rf htmlcov
	@PATH=test/coverage_python:${PATH} python test/test_autopep8.py
	@coverage combine
	@coverage report
	@coverage html
	@echo 'Coverage report: htmlcov/index.html'
	@rm .coverage

check:
	pep8 autopep8.py && echo 'OK'
	pylint --reports=no --include-ids=yes --disable=C0111,C0103,R0902,W0511,R0914,R0912,R0915,R0904 --rcfile=/dev/null autopep8.py && echo 'OK'

pypireg:
	python setup.py register
	python setup.py sdist upload

clean:
	rm -rf .tmp.test.py
	rm -rf temp
	rm -rf *.pyc
	rm -rf *egg-info dist build
