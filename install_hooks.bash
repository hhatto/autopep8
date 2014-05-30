#!/bin/bash -ex

readonly ROOT=$(dirname "$0")
cd "$ROOT"/.git/hooks
ln -fs ../../hooks/* .
