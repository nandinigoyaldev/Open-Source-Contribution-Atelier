export interface ICache<T> {
  get(key: string): T | undefined;
  set(key: string, value: T, ttlMs?: number): void;
  invalidate(key: string): void;
  clear(): void;
}

interface CacheNode<T> {
  key: string;
  value: T;
  expiresAt: number | null;
  next: CacheNode<T> | null;
  prev: CacheNode<T> | null;
}

/**
 * LRU (Least Recently Used) Cache implementation with optional TTL (Time-To-Live).
 */
export class LRUCache<T> implements ICache<T> {
  private capacity: number;
  private map: Map<string, CacheNode<T>>;
  private head: CacheNode<T> | null;
  private tail: CacheNode<T> | null;
  private defaultTtlMs: number | null;

  constructor(capacity: number = 100, defaultTtlMs: number | null = null) {
    if (capacity <= 0) {
      throw new Error("Capacity must be greater than 0");
    }
    this.capacity = capacity;
    this.map = new Map();
    this.head = null;
    this.tail = null;
    this.defaultTtlMs = defaultTtlMs;
  }

  public get(key: string): T | undefined {
    const node = this.map.get(key);
    if (!node) return undefined;

    // Check TTL
    if (node.expiresAt !== null && Date.now() > node.expiresAt) {
      this.removeNode(node);
      this.map.delete(key);
      return undefined;
    }

    // Move to front (most recently used)
    this.moveToFront(node);
    return node.value;
  }

  public set(key: string, value: T, ttlMs?: number): void {
    let node = this.map.get(key);
    const ttl = ttlMs !== undefined ? ttlMs : this.defaultTtlMs;
    const expiresAt = ttl !== null ? Date.now() + ttl : null;

    if (node) {
      node.value = value;
      node.expiresAt = expiresAt;
      this.moveToFront(node);
    } else {
      node = { key, value, expiresAt, next: null, prev: null };

      if (this.map.size >= this.capacity) {
        this.evictLeastRecentlyUsed();
      }

      this.map.set(key, node);
      this.addToFront(node);
    }
  }

  public invalidate(key: string): void {
    const node = this.map.get(key);
    if (node) {
      this.removeNode(node);
      this.map.delete(key);
    }
  }

  public clear(): void {
    this.map.clear();
    this.head = null;
    this.tail = null;
  }

  private moveToFront(node: CacheNode<T>): void {
    if (this.head === node) return; // Already at the front

    this.removeNode(node);
    this.addToFront(node);
  }

  private addToFront(node: CacheNode<T>): void {
    node.next = this.head;
    node.prev = null;

    if (this.head) {
      this.head.prev = node;
    }
    this.head = node;

    if (!this.tail) {
      this.tail = node;
    }
  }

  private removeNode(node: CacheNode<T>): void {
    if (node.prev) {
      node.prev.next = node.next;
    } else {
      this.head = node.next; // Node is the head
    }

    if (node.next) {
      node.next.prev = node.prev;
    } else {
      this.tail = node.prev; // Node is the tail
    }
  }

  private evictLeastRecentlyUsed(): void {
    if (this.tail) {
      this.map.delete(this.tail.key);
      this.removeNode(this.tail);
    }
  }
}
