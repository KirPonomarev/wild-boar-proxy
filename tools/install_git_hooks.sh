#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
hooks_path="$repo_root/.githooks"

git config core.hooksPath "$hooks_path"
echo "Configured git hooks path: $hooks_path"
