/**
 * E2E encryption utilities for direct messages using libsodium-wrappers.
 *
 * Encryption scheme:
 *   - Key generation: X25519 (Curve25519 Diffie-Hellman)
 *   - Encryption:     XSalsa20-Poly1305 authenticated box encryption
 *   - Key storage:    Private key stored in localStorage (base64). Public key
 *                     registered with the server at /api/chat/public-keys/.
 *
 * The server NEVER sees plaintext. It only stores:
 *   - encrypted_content (base64 ciphertext)
 *   - nonce (base64 24-byte random nonce)
 *   - recipient's public key (fetched from the public key registry)
 */

import _sodium from "libsodium-wrappers";

const PRIVATE_KEY_STORAGE_KEY = "e2e_private_key";
const PUBLIC_KEY_STORAGE_KEY = "e2e_public_key";

let sodiumReady = false;

async function getSodium() {
  if (!sodiumReady) {
    await _sodium.ready;
    sodiumReady = true;
  }
  return _sodium;
}

/** Generate a new X25519 key pair and persist it in localStorage. */
export async function generateAndStoreKeyPair(): Promise<{
  publicKey: string;
  privateKey: string;
}> {
  const sodium = await getSodium();
  const keyPair = sodium.crypto_box_keypair();

  const publicKeyB64 = sodium.to_base64(
    keyPair.publicKey,
    sodium.base64_variants.ORIGINAL
  );
  const privateKeyB64 = sodium.to_base64(
    keyPair.privateKey,
    sodium.base64_variants.ORIGINAL
  );

  localStorage.setItem(PUBLIC_KEY_STORAGE_KEY, publicKeyB64);
  localStorage.setItem(PRIVATE_KEY_STORAGE_KEY, privateKeyB64);

  return { publicKey: publicKeyB64, privateKey: privateKeyB64 };
}

/** Return stored key pair, or generate one if none exists. */
export async function getOrCreateKeyPair(): Promise<{
  publicKey: string;
  privateKey: string;
}> {
  const storedPublic = localStorage.getItem(PUBLIC_KEY_STORAGE_KEY);
  const storedPrivate = localStorage.getItem(PRIVATE_KEY_STORAGE_KEY);
  if (storedPublic && storedPrivate) {
    return { publicKey: storedPublic, privateKey: storedPrivate };
  }
  return generateAndStoreKeyPair();
}

/**
 * Encrypt a plaintext message for a recipient.
 *
 * @param plaintext          The message string to encrypt.
 * @param recipientPublicKeyB64  The recipient's base64-encoded X25519 public key.
 * @returns { encryptedContent, nonce } — both base64-encoded — safe to send to the server.
 */
export async function encryptMessage(
  plaintext: string,
  recipientPublicKeyB64: string
): Promise<{ encryptedContent: string; nonce: string }> {
  const sodium = await getSodium();
  const { privateKey: senderPrivateKeyB64 } = await getOrCreateKeyPair();

  const recipientPublicKey = sodium.from_base64(
    recipientPublicKeyB64,
    sodium.base64_variants.ORIGINAL
  );
  const senderPrivateKey = sodium.from_base64(
    senderPrivateKeyB64,
    sodium.base64_variants.ORIGINAL
  );

  const nonce = sodium.randombytes_buf(sodium.crypto_box_NONCEBYTES);
  const messageBytes = sodium.from_string(plaintext);

  const ciphertext = sodium.crypto_box_easy(
    messageBytes,
    nonce,
    recipientPublicKey,
    senderPrivateKey
  );

  return {
    encryptedContent: sodium.to_base64(
      ciphertext,
      sodium.base64_variants.ORIGINAL
    ),
    nonce: sodium.to_base64(nonce, sodium.base64_variants.ORIGINAL),
  };
}

/**
 * Decrypt a received message.
 *
 * @param encryptedContentB64  Base64-encoded ciphertext from the server.
 * @param nonceB64             Base64-encoded nonce from the server.
 * @param senderPublicKeyB64   The sender's base64-encoded X25519 public key.
 * @returns The decrypted plaintext string.
 * @throws Error if decryption fails (wrong key, tampered data, etc.)
 */
export async function decryptMessage(
  encryptedContentB64: string,
  nonceB64: string,
  senderPublicKeyB64: string
): Promise<string> {
  const sodium = await getSodium();
  const { privateKey: recipientPrivateKeyB64 } = await getOrCreateKeyPair();

  const ciphertext = sodium.from_base64(
    encryptedContentB64,
    sodium.base64_variants.ORIGINAL
  );
  const nonce = sodium.from_base64(nonceB64, sodium.base64_variants.ORIGINAL);
  const senderPublicKey = sodium.from_base64(
    senderPublicKeyB64,
    sodium.base64_variants.ORIGINAL
  );
  const recipientPrivateKey = sodium.from_base64(
    recipientPrivateKeyB64,
    sodium.base64_variants.ORIGINAL
  );

  const decrypted = sodium.crypto_box_open_easy(
    ciphertext,
    nonce,
    senderPublicKey,
    recipientPrivateKey
  );

  if (!decrypted) {
    throw new Error("Decryption failed — message may be corrupted or tampered.");
  }

  return sodium.to_string(decrypted);
}

/** Wipe the locally stored key pair. Used on logout. */
export function clearLocalKeyPair(): void {
  localStorage.removeItem(PUBLIC_KEY_STORAGE_KEY);
  localStorage.removeItem(PRIVATE_KEY_STORAGE_KEY);
}
