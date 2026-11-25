// Make a password hash for the Cloudflare secrets OWNER_HASH / ADMIN_HASH.
//   node tools/make-hash.mjs "the password"
import { makeHash } from "../lib/auth.js";
const p = process.argv[2];
if (!p) { console.error('usage: node tools/make-hash.mjs "password"'); process.exit(1); }
console.log(await makeHash(p));
