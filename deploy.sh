#!/bin/bash
set -eu

if [[ $# -ne 1 ]]; then
	echo >&2 "Usage: $0 statbot-config.yaml"
	exit 1
fi

repo_dir="$(dirname "$0")"
dest_dir=~statbot/repo

mkdir -p "$dest_dir"
cp -a "$repo_dir" "$dest_dir"
install -m400 "$1" "$dest_dir/config.yaml"
chown -R statbot:statbot "$dest_dir"
echo "Installed source code to '$dest_dir'"

python3.6 -m pip install -r "$repo_dir/requirements.txt"
echo "Installed Python dependencies"

install -m644 "$repo_dir/misc/statbot.service" /etc/systemd/system/statbot.service
chown root:root /etc/systemd/system/statbot.service
echo "Installed systemd service"

systemctl daemon-reload
systemctl restart statbot.service
echo "Started statbot systemd service"

