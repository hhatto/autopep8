all:
	@echo "make pypireg"


TEST_DIR=test
.PHONY: test_basic test_diff test_unit
test: test_basic test_diff test_unit

test_basic:
	@echo '--->  Running basic test'
	python autopep8.py test_target.py > .tmp.test.py
	pep8 -r .tmp.test.py
	rm .tmp.test.py

test_diff:
	@echo '--->  Running --diff test'
	cp test_target.py .tmp.test_target.py
	python autopep8.py --diff .tmp.test_target.py > .tmp.test_target.py.patch
	patch < .tmp.test_target.py.patch
	rm .tmp.test_target.py.patch
	pep8 -r .tmp.test_target.py
	rm .tmp.test_target.py

test_unit:
	@echo '--->  Running unit tests'
	python test/test_autopep8.py

pypireg:
	python setup.py register
	python setup.py sdist upload

clean:
	rm -rf .tmp.test.py
	rm -rf temp
	rm -rf *.pyc
	rm -rf *egg-info dist build
