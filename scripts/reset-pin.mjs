const ITERATIONS = 100_000;
const KEY_LENGTH = 32;
const DIGEST = 'SHA-256';

function printUsage() {
	console.log('Usage: pnpm run pin:reset -- --creator-id <id> --pin <new-pin>');
	console.log('   or: pnpm run pin:reset -- --name <creator-name> --pin <new-pin>');
	console.log('Optional: --database-url <url> (defaults to DATABASE_URL or file:local.db)');
}

function getArgValue(args, key) {
	const index = args.indexOf(key);
	if (index === -1) return undefined;
	return args[index + 1];
}

function bufToHex(buf) {
	return Array.from(new Uint8Array(buf))
		.map((b) => b.toString(16).padStart(2, '0'))
		.join('');
}

async function hashPin(pin) {
	const salt = crypto.getRandomValues(new Uint8Array(16));
	const keyMaterial = await crypto.subtle.importKey(
		'raw',
		new TextEncoder().encode(pin),
		'PBKDF2',
		false,
		['deriveBits']
	);
	const bits = await crypto.subtle.deriveBits(
		{ name: 'PBKDF2', salt: salt.buffer, iterations: ITERATIONS, hash: DIGEST },
		keyMaterial,
		KEY_LENGTH * 8
	);
	return `${bufToHex(salt.buffer)}:${bufToHex(bits)}`;
}

async function main() {
	const args = process.argv.slice(2);
	if (args.includes('--help') || args.includes('-h')) {
		printUsage();
		process.exit(0);
	}

	const creatorIdRaw = getArgValue(args, '--creator-id');
	const name = getArgValue(args, '--name');
	const pin = getArgValue(args, '--pin');
	const databaseUrl =
		getArgValue(args, '--database-url') ?? process.env.DATABASE_URL ?? 'file:local.db';

	if (!pin) {
		console.error('Missing required argument: --pin');
		printUsage();
		process.exit(1);
	}

	if ((creatorIdRaw && name) || (!creatorIdRaw && !name)) {
		console.error('Provide exactly one identifier: --creator-id or --name');
		printUsage();
		process.exit(1);
	}

	const { createClient } = await import('@libsql/client');
	const client = createClient({ url: databaseUrl });

	try {
		let creator;
		if (creatorIdRaw) {
			const creatorId = Number.parseInt(creatorIdRaw, 10);
			if (Number.isNaN(creatorId)) {
				console.error('--creator-id must be an integer');
				process.exit(1);
			}
			const result = await client.execute({
				sql: 'select id, name from creators where id = ? limit 1',
				args: [creatorId]
			});
			creator = result.rows[0];
		} else {
			const result = await client.execute({
				sql: 'select id, name from creators where name = ? limit 2',
				args: [name]
			});
			if (result.rows.length > 1) {
				console.error(`Multiple creators found with name "${name}". Use --creator-id instead.`);
				process.exit(1);
			}
			creator = result.rows[0];
		}

		if (!creator) {
			console.error('Creator not found');
			process.exit(1);
		}

		const passwordHash = await hashPin(pin);
		await client.execute({
			sql: 'update creators set password_hash = ? where id = ?',
			args: [passwordHash, creator.id]
		});

		console.log(`PIN reset for creator #${creator.id} (${creator.name})`);
	} finally {
		client.close();
	}
}

main().catch((error) => {
	console.error('Failed to reset PIN:', error);
	process.exit(1);
});
