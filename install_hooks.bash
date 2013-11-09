#!/bin/bash -ex

root=$(dirname "$0")
cd "$root"/.git/hooks
ln -s ../../hooks/* .
