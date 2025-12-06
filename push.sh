#!/bin/bash
# Quick push script for Hikvision ISAPI integration
cd "$(dirname "$0")"
git add -A
git commit -m "Auto-commit: $(date '+%Y-%m-%d %H:%M:%S')" || echo "No changes to commit"
git push origin main

