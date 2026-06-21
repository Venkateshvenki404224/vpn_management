# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Unix-socket client for the wg-agent sidecar.

The unprivileged worker never runs ``wg``/``wg-quick`` itself. It sends a JSON
``{"verb", "args"}`` request over the shared-volume socket and the root-run
agent re-validates and executes it. Transport failures raise
:class:`VpnAgentError`; a command that *ran* but failed comes back as a normal
reply with ``ok = False`` for the caller to interpret.
"""

import json
import socket

SOCKET_PATH = "/run/wg-agent/agent.sock"
DEFAULT_TIMEOUT = 30
MAX_REPLY = 1024 * 1024


class VpnAgentError(Exception):
	"""The wg-agent socket was unreachable, timed out, or replied malformed."""


def call(verb, args, timeout=DEFAULT_TIMEOUT, socket_path=SOCKET_PATH):
	"""Send a verb to the agent and return its parsed JSON reply."""
	request = json.dumps({"verb": verb, "args": args}).encode("utf-8")
	raw = _exchange(request, timeout, socket_path)
	try:
		return json.loads(raw.decode("utf-8"))
	except ValueError as error:
		raise VpnAgentError(f"malformed reply from wg-agent: {error}")


def _exchange(request, timeout, socket_path):
	try:
		with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
			client.settimeout(timeout)
			client.connect(socket_path)
			client.sendall(request)
			client.shutdown(socket.SHUT_WR)
			return _read_reply(client)
	except OSError as error:
		raise VpnAgentError(f"cannot reach wg-agent at {socket_path}: {error}")


def _read_reply(client):
	chunks = []
	size = 0
	while True:
		chunk = client.recv(65536)
		if not chunk:
			break
		size += len(chunk)
		if size > MAX_REPLY:
			raise VpnAgentError("reply from wg-agent too large")
		chunks.append(chunk)
	return b"".join(chunks)
