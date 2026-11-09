# Security Notes

- Authentication uses Django/DRF tokens and BcryptSHA256 for newly created passwords.
- Dashboard write operations use role-based permission classes.
- Telemetry serializers enforce numeric bounds, including non-negative latency and packet loss.
- Healing commands are checked for dangerous patterns and validated with a network-disabled, read-only Docker sandbox before connector execution.
- FRR management traffic uses SSH on the management interface; failure injection must use the separate data interface `eth1`.
- Production deployment must terminate HTTPS/TLS at a reverse proxy and set secure cookie, HSTS, and trusted-origin settings through environment variables.
- Credentials in local development defaults are for the included Docker testbed only and must be replaced for real infrastructure.
