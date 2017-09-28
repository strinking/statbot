#!/bin/bash
set -eu

repo_dir="$(dirname "$0")"
dest_dir=~statbot/dev

cp -a "$repo_dir" "$dest_dir"
chown -R statbot "$dest_dir"
install -m644 "$repo_dir/misc/statbot.service" /etc/systemd/system/statbot.service

systemctl daemon-reload
systemctl restart statbot.service

