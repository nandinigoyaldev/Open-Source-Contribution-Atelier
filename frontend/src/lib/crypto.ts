/**
 * Web Crypto API utilities for End-to-End Encryption using ECDH and AES-GCM.
 */

export type KeyPair = CryptoKeyPair;

export async function generateKeyPair(): Promise<KeyPair> {
  return window.crypto.subtle.generateKey(
    {
      name: "ECDH",
      namedCurve: "P-256",
    },
    true,
    ["deriveKey", "deriveBits"],
  );
}

export async function exportPublicKey(key: CryptoKey): Promise<string> {
  const exported = await window.crypto.subtle.exportKey("spki", key);
  const exportedAsString = String.fromCharCode.apply(
    null,
    Array.from(new Uint8Array(exported)),
  );
  return btoa(exportedAsString);
}

export async function importPublicKey(base64Key: string): Promise<CryptoKey> {
  const binaryDerString = atob(base64Key);
  const binaryDer = new Uint8Array(binaryDerString.length);
  for (let i = 0; i < binaryDerString.length; i++) {
    binaryDer[i] = binaryDerString.charCodeAt(i);
  }

  return window.crypto.subtle.importKey(
    "spki",
    binaryDer.buffer,
    {
      name: "ECDH",
      namedCurve: "P-256",
    },
    true,
    [],
  );
}

export async function deriveSharedKey(
  privateKey: CryptoKey,
  publicKey: CryptoKey,
): Promise<CryptoKey> {
  return window.crypto.subtle.deriveKey(
    {
      name: "ECDH",
      public: publicKey,
    },
    privateKey,
    {
      name: "AES-GCM",
      length: 256,
    },
    false,
    ["encrypt", "decrypt"],
  );
}

export async function encryptMessage(
  message: string,
  key: CryptoKey,
): Promise<{ ciphertext: string; iv: string }> {
  const encoded = new TextEncoder().encode(message);
  const iv = window.crypto.getRandomValues(new Uint8Array(12));
  const ciphertext = await window.crypto.subtle.encrypt(
    {
      name: "AES-GCM",
      iv: iv,
    },
    key,
    encoded,
  );

  return {
    ciphertext: btoa(
      String.fromCharCode.apply(null, Array.from(new Uint8Array(ciphertext))),
    ),
    iv: btoa(String.fromCharCode.apply(null, Array.from(iv))),
  };
}

export async function decryptMessage(
  ciphertextBase64: string,
  ivBase64: string,
  key: CryptoKey,
): Promise<string> {
  const ciphertextStr = atob(ciphertextBase64);
  const ciphertext = new Uint8Array(ciphertextStr.length);
  for (let i = 0; i < ciphertextStr.length; i++) {
    ciphertext[i] = ciphertextStr.charCodeAt(i);
  }

  const ivStr = atob(ivBase64);
  const iv = new Uint8Array(ivStr.length);
  for (let i = 0; i < ivStr.length; i++) {
    iv[i] = ivStr.charCodeAt(i);
  }

  const decrypted = await window.crypto.subtle.decrypt(
    {
      name: "AES-GCM",
      iv: iv,
    },
    key,
    ciphertext.buffer,
  );

  return new TextDecoder().decode(decrypted);
}
