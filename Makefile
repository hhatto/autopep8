all:
	@echo "make pypireg"


TEST_DIR=test
.PHONY: test
test:
	python autopep8.py test_target.py > .tmp.test.py
	pep8 -r .tmp.test.py
	rm .tmp.test.py
	# Test --diff
	cp test_target.py .tmp.test_target.py
	python autopep8.py --diff .tmp.test_target.py > .tmp.test_target.py.patch
	patch < .tmp.test_target.py.patch
	rm .tmp.test_target.py.patch
	pep8 -r .tmp.test_target.py
	rm .tmp.test_target.py

pypireg:
	python setup.py register
	python setup.py sdist upload

clean:
	rm -rf .tmp.test.py
	rm -rf temp
	rm -rf *.pyc
	rm -rf *egg-info dist build
