#!/bin/sh
export MECABRC="$(mecab-config --sysconfdir)/mecabrc"
exec "$@"
