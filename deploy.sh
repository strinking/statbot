#!/bin/bash
set -eu

if [[ $# -ne 1 ]]; then
	echo >&2 "Usage: $0 statbot-config.json"
	exit 1
fi

repo_dir="$(dirname "$0")"
dest_dir=~statbot/repo

mkdir -p "$dest_dir"
cp -a "$repo_dir" "$dest_dir"
chown -R statbot "$dest_dir"
install -m644 "$1" "$dest_dir/config.json"
install -m644 "$repo_dir/misc/statbot.service" /etc/systemd/system/statbot.service

systemctl daemon-reload
systemctl restart statbot.service

