/**
 * Web Crypto API implementation for end-to-end encrypted notes.
 */

// We store the derived/generated AES-GCM key in IndexedDB to persist it securely
// across sessions for the same user/browser without storing it in plaintext on disk if possible,
// but for simplicity in a browser context, localForage or raw IndexedDB works well.
// Here we just use IndexedDB directly via a simple wrapper.

const DB_NAME = "atelier_crypto";
const DB_STORE = "keys";
const KEY_NAME = "master_notes_key";

async function getDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => {
      request.result.createObjectStore(DB_STORE);
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function saveKeyToDB(key: CryptoKey): Promise<void> {
  const db = await getDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(DB_STORE, "readwrite");
    const store = transaction.objectStore(DB_STORE);
    const request = store.put(key, KEY_NAME);
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

async function getKeyFromDB(): Promise<CryptoKey | null> {
  const db = await getDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(DB_STORE, "readonly");
    const store = transaction.objectStore(DB_STORE);
    const request = store.get(KEY_NAME);
    request.onsuccess = () => resolve(request.result || null);
    request.onerror = () => reject(request.error);
  });
}

/**
 * Initializes or retrieves the AES-GCM master key for notes encryption.
 */
export async function getOrGenerateNotesKey(): Promise<CryptoKey> {
  let key = await getKeyFromDB();
  if (!key) {
    key = await window.crypto.subtle.generateKey(
      {
        name: "AES-GCM",
        length: 256,
      },
      true,
      ["encrypt", "decrypt"],
    );
    await saveKeyToDB(key);
  }
  return key;
}

// Helpers for Base64 <-> Uint8Array
function arrayBufferToBase64(buffer: ArrayBuffer): string {
  let binary = "";
  const bytes = new Uint8Array(buffer);
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return window.btoa(binary);
}

function base64ToArrayBuffer(base64: string): ArrayBuffer {
  const binary_string = window.atob(base64);
  const len = binary_string.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    bytes[i] = binary_string.charCodeAt(i);
  }
  return bytes.buffer;
}

/**
 * Encrypts plaintext and returns base64 ciphertext and IV.
 */
export async function encryptNoteContent(
  plaintext: string,
): Promise<{ ciphertext: string; iv: string }> {
  const key = await getOrGenerateNotesKey();
  const iv = window.crypto.getRandomValues(new Uint8Array(12));
  const encodedPlaintext = new TextEncoder().encode(plaintext);

  const ciphertextBuffer = await window.crypto.subtle.encrypt(
    {
      name: "AES-GCM",
      iv: iv,
    },
    key,
    encodedPlaintext,
  );

  return {
    ciphertext: arrayBufferToBase64(ciphertextBuffer),
    iv: arrayBufferToBase64(iv.buffer),
  };
}

/**
 * Decrypts base64 ciphertext using the stored key and IV.
 */
export async function decryptNoteContent(
  ciphertextBase64: string,
  ivBase64: string,
): Promise<string> {
  try {
    const key = await getOrGenerateNotesKey();
    const ciphertext = base64ToArrayBuffer(ciphertextBase64);
    const iv = base64ToArrayBuffer(ivBase64);

    const decryptedBuffer = await window.crypto.subtle.decrypt(
      {
        name: "AES-GCM",
        iv: new Uint8Array(iv),
      },
      key,
      ciphertext,
    );

    return new TextDecoder().decode(decryptedBuffer);
  } catch (error) {
    console.error("Failed to decrypt note:", error);
    return "⚠️ [Encrypted content cannot be read - missing or invalid key]";
  }
}
