# Development & testing

Local tooling, research notes, and camera diagnostics for the Hikvision ISAPI integration. **Not required for HACS install** — only `custom_components/hikvision_isapi/` ships with the integration.

**New chat / agent context:** see workspace [`dev/context/README.md`](../../dev/context/README.md) (workflow, cameras, release process).

| Folder | Contents |
| ------ | -------- |
| `research/` | Endpoint analysis, entity mapping notes, audio/firmware research, integration TODO |
| `scripts/` | Standalone Python utilities (`query_camera_capabilities.py`, config porting, etc.) |
| `scripts/test-endpoints/` | Ad-hoc ISAPI probe scripts (gitignored) |
| `tools/` | `audio_converter.html` and other one-off helpers |
| `reference/` | ISAPI PDF/text reference copies (large files gitignored) |
| `captures/` | Camera XML backups, capability JSON dumps, BSP logs (gitignored) |
| `local/` | Personal configs and notes (gitignored) |

## Quick commands

```bash
# Probe what a camera supports
python3 dev/scripts/query_camera_capabilities.py 192.168.1.13 admin 'your-password'

# Run endpoint tests (from repo root)
python3 dev/scripts/test-endpoints/test_endpoints.py
```
