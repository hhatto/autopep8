#!/bin/bash
#
# Run acid test against latest packages on PyPi.

# Check all packages released in the last $LAST_HOURS hours
LAST_HOURS=100

# Assume we are running from the correct directory
ACID="$PWD/acid.py"
TMP_DIR="$PWD/pypi_tmp"
mkdir "$TMP_DIR"

for package in $(yolk -C "$LAST_HOURS" | grep -v '^	' | sed 's/ .*//')
do
    echo
    echo "$package"

    mkdir "$TMP_DIR/$package"
    if [ $? -ne 0 ]
    then
        echo 'Skipping already checked package'
        continue;
    fi

    cd "$TMP_DIR/$package"

    yolk --fetch-package="$package"
    if [ $? -ne 0 ]
    then
        echo 'ERROR: yolk failed'
        continue;
    fi

    tar xf "$package"*.tar.gz
    if [ $? -ne 0 ]
    then
        unzip -q "$package"*.zip
        if [ $? -ne 0 ]
        then
            echo 'ERROR: Both untar and unzip failed'
            continue;
        fi
    fi

    "$ACID" "$TMP_DIR/$package"
    if [ $? -ne 0 ]
    then
        break;
    fi
done
