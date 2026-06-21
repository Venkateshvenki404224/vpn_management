# The single VPN-server sidecar: WireGuard tooling + a stdlib-only Python agent.
FROM debian:bookworm-slim

RUN apt-get update \
	&& apt-get install -y --no-install-recommends \
		wireguard-tools \
		iproute2 \
		iptables \
		procps \
		python3 \
	&& rm -rf /var/lib/apt/lists/*

COPY agentd /opt/wg-agent/agentd
COPY entrypoint /usr/local/bin/entrypoint
RUN chmod +x /opt/wg-agent/agentd /usr/local/bin/entrypoint

ENTRYPOINT ["/usr/local/bin/entrypoint"]
