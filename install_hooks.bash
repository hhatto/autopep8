#!/bin/bash -ex

readonly root=$(dirname "$0")
cd "$root"/.git/hooks
ln -fs ../../hooks/* .
