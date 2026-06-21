// Human-readable byte counts for the rx/tx transfer columns.
export function humanBytes(value) {
	const bytes = Number(value) || 0;
	if (bytes <= 0) return "0 B";
	const units = ["B", "KB", "MB", "GB", "TB", "PB"];
	const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
	const size = bytes / 1024 ** exponent;
	const digits = exponent === 0 || size >= 100 ? 0 : 1;
	return `${size.toFixed(digits)} ${units[exponent]}`;
}

// Coarse "x minutes ago" for the last-handshake column.
export function relativeTime(value) {
	if (!value) return "Never";
	const then = new Date(String(value).replace(" ", "T"));
	if (Number.isNaN(then.getTime())) return String(value);
	const seconds = Math.round((Date.now() - then.getTime()) / 1000);
	if (seconds < 5) return "just now";
	const units = [
		["year", 31536000],
		["month", 2592000],
		["day", 86400],
		["hour", 3600],
		["minute", 60],
		["second", 1],
	];
	for (const [name, span] of units) {
		const amount = Math.floor(seconds / span);
		if (amount >= 1) return `${amount} ${name}${amount === 1 ? "" : "s"} ago`;
	}
	return "just now";
}
