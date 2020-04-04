#!/bin/bash
set -eu

if [[ $# -ne 1 ]]; then
	echo >&2 "Usage: $0 statbot-config.yaml"
	exit 1
fi

python_ver=python3.8
repo_dir="$(dirname "$0")"
dest_dir=~statbot/repo

if [[ -f "$repo_dir/statbot.service" ]]; then
	service="$repo_dir/statbot.service"
else
	service="$repo_dir/misc/statbot.service"
fi

rm -r "$dest_dir"
mkdir -p "$dest_dir"
cp -a "$repo_dir" "$dest_dir"
install -m400 "$1" "$dest_dir/config.yaml"
chown -R statbot:statbot "$dest_dir"
echo "Installed source code to '$dest_dir'"

"$python_ver" -m pip install -r "$repo_dir/requirements.txt"
echo "Installed Python dependencies"

install -m644 "$service" /usr/local/lib/systemd/system/statbot.service
chown root:root /usr/local/lib/systemd/system/statbot.service
echo "Installed systemd service"

systemctl daemon-reload
systemctl restart statbot.service
echo "Started statbot systemd service"
