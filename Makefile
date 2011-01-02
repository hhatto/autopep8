all:
	@echo "make pypireg"


TEST_DIR=test
.PHONY: test
test:
	python autopep8.py test_target.py > .tmp.test.py
	pep8 -r .tmp.test.py
	rm .tmp.test.py

pypireg:
	python setup.py register
	python setup.py sdist upload

clean:
	rm -rf .tmp.test.py
	rm -rf *.pyc
