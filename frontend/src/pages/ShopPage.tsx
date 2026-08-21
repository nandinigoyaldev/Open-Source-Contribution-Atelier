import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchApi } from "../lib/api";
import toast from "react-hot-toast";
import {
  Coins,
  Gift,
  Loader2,
  CheckCircle2,
  Sparkles,
  ShoppingBag,
  Lock,
  ArrowLeft,
  Zap,
  Palette,
  Award,
  Crown,
  Package,
  ShieldAlert,
  Flame,
  Check,
} from "lucide-react";
import { Link } from "react-router-dom";
import { CARD_FOCUS_RING } from "../lib/a11yFocus";
import { Skeleton } from "../components/ui/Skeleton";

export interface ShopItemData {
  id: number;
  name: string;
  description: string;
  item_type: string;
  cost: number;
  icon_emoji: string;
  is_limited: boolean;
  already_purchased: boolean;
  rarity?: "COMMON" | "RARE" | "EPIC" | "LEGENDARY" | "MYTHIC";
  benefit?: string;
}

export interface PurchaseResponse {
  success: boolean;
  item: string;
  xp_spent: number;
  remaining_xp: number;
}

const DEFAULT_SHOP_ITEMS: ShopItemData[] = [
  {
    id: 101,
    name: "Flame Saver (Streak Freeze)",
    description: "Protects your daily activity streak from breaking if you miss 1 day of contributing.",
    item_type: "streak_freeze",
    cost: 150,
    icon_emoji: "🔥",
    is_limited: true,
    already_purchased: false,
    rarity: "EPIC",
    benefit: "1 Day Streak Shield",
  },
  {
    id: 102,
    name: "2x XP Multiplier Boost (24 Hours)",
    description: "Doubles all XP earned from completing lessons, quizzes, and pull requests for 24 hours.",
    item_type: "xp_boost",
    cost: 300,
    icon_emoji: "⚡",
    is_limited: false,
    already_purchased: false,
    rarity: "RARE",
    benefit: "+100% Bonus XP",
  },
  {
    id: 103,
    name: "Neobrutalist Cyberpunk Theme",
    description: "Unlocks an exclusive high-contrast Cyberpunk neon dark theme across your entire Atelier UI.",
    item_type: "profile_theme",
    cost: 500,
    icon_emoji: "🎨",
    is_limited: true,
    already_purchased: false,
    rarity: "LEGENDARY",
    benefit: "Exclusive UI Theme",
  },
  {
    id: 104,
    name: "ECSoC '26 Diamond Contributor Badge",
    description: "Showcase an official ECSoC 2026 Diamond Contributor badge on your profile and PR certificate comments.",
    item_type: "badge_unlock",
    cost: 750,
    icon_emoji: "💎",
    is_limited: true,
    already_purchased: false,
    rarity: "MYTHIC",
    benefit: "Profile & PR Badge",
  },
  {
    id: 105,
    name: "Title: Master Architect 🛠️",
    description: "Equip a custom title string next to your username on global leaderboards and forum comments.",
    item_type: "custom_title",
    cost: 250,
    icon_emoji: "👑",
    is_limited: false,
    already_purchased: false,
    rarity: "RARE",
    benefit: "Custom Name Title",
  },
  {
    id: 106,
    name: "Fast-Track PR Review Ticket 🚀",
    description: "Grants priority maintainer review queue placement for your open ECSoC Pull Request.",
    item_type: "perk",
    cost: 400,
    icon_emoji: "🚀",
    is_limited: true,
    already_purchased: false,
    rarity: "EPIC",
    benefit: "Priority PR Review",
  },
  {
    id: 107,
    name: "Golden Terminal Cursor Glow ✨",
    description: "Adds an animated glowing golden cursor effect inside the Contributor Sandbox code editor.",
    item_type: "cosmetic",
    cost: 350,
    icon_emoji: "✨",
    is_limited: false,
    already_purchased: false,
    rarity: "RARE",
    benefit: "Editor Visual FX",
  },
  {
    id: 108,
    name: "Official Contributor Sticker Pack 📦",
    description: "Unlocks high-resolution SVG sticker assets for your GitHub README and developer portfolio.",
    item_type: "perk",
    cost: 200,
    icon_emoji: "📦",
    is_limited: false,
    already_purchased: false,
    rarity: "COMMON",
    benefit: "Digital Asset Pack",
  },
];

const RARITY_BADGE_STYLES: Record<string, string> = {
  COMMON: "bg-gray-200 text-gray-900 border-black",
  RARE: "bg-blue-300 text-black border-black",
  EPIC: "bg-purple-300 text-black border-black",
  LEGENDARY: "bg-amber-300 text-black border-black",
  MYTHIC: "bg-pink-400 text-black border-black",
};

const CATEGORIES = [
  { id: "all", label: "All Items 🛍️" },
  { id: "streak_freeze", label: "Streak 🛡️" },
  { id: "xp_boost", label: "Boosts ⚡" },
  { id: "profile_theme", label: "Themes 🎨" },
  { id: "badge_unlock", label: "Badges 💎" },
  { id: "custom_title", label: "Titles 👑" },
  { id: "perk", label: "Perks 🚀" },
];

export function ShopPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<"store" | "vault">("store");
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [purchasingId, setPurchasingId] = useState<number | null>(null);
  const [confirmItem, setConfirmItem] = useState<ShopItemData | null>(null);
  const [equippedItemIds, setEquippedItemIds] = useState<number[]>(() => {
    try {
      const saved = localStorage.getItem("equipped_shop_items");
      return saved ? JSON.parse(saved) : [101];
    } catch {
      return [101];
    }
  });

  // Local Storage Inventory for Demo & Offline support
  const [localInventory, setLocalInventory] = useState<number[]>(() => {
    try {
      const saved = localStorage.getItem("purchased_shop_items");
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  // Fetch shop items from backend with DEFAULT_SHOP_ITEMS fallback
  const { data: apiItems, isLoading } = useQuery<ShopItemData[]>({
    queryKey: ["shopItems"],
    queryFn: async () => {
      try {
        const res = (await fetchApi("/gamification/shop/", {
          suppressErrorToast: true,
        })) as ShopItemData[];
        return Array.isArray(res) && res.length > 0 ? res : DEFAULT_SHOP_ITEMS;
      } catch {
        return DEFAULT_SHOP_ITEMS;
      }
    },
  });

  // Fetch total user XP
  const { data: userXpData } = useQuery<{ total_xp: number }>({
    queryKey: ["myTotalXp"],
    queryFn: async () => {
      try {
        return (await fetchApi("/gamification/my-xp/", {
          suppressErrorToast: true,
        })) as { total_xp: number };
      } catch {
        return { total_xp: 1250 };
      }
    },
  });

  const [availableXp, setAvailableXp] = useState<number>(() => {
    const savedXp = localStorage.getItem("user_custom_xp");
    return savedXp ? parseInt(savedXp, 10) : userXpData?.total_xp ?? 1250;
  });

  // Sync API XP if available
  const currentXp = userXpData?.total_xp ?? availableXp;

  const catalogItems = useMemo(() => {
    const items = apiItems || DEFAULT_SHOP_ITEMS;
    return items.map((item) => ({
      ...item,
      already_purchased: item.already_purchased || localInventory.includes(item.id),
      rarity: item.rarity || "RARE",
    }));
  }, [apiItems, localInventory]);

  const filteredItems = useMemo(() => {
    if (selectedCategory === "all") return catalogItems;
    return catalogItems.filter((i) => i.item_type === selectedCategory);
  }, [catalogItems, selectedCategory]);

  const ownedItems = useMemo(() => {
    return catalogItems.filter((i) => i.already_purchased);
  }, [catalogItems]);

  const purchaseMutation = useMutation({
    mutationFn: async (itemId: number) => {
      try {
        return (await fetchApi("/gamification/shop/purchase/", {
          method: "POST",
          body: JSON.stringify({ item_id: itemId }),
          headers: { "Content-Type": "application/json" },
        })) as PurchaseResponse;
      } catch {
        // Fallback optimistic purchase
        const target = catalogItems.find((i) => i.id === itemId);
        if (!target) throw new Error("Item not found");
        if (currentXp < target.cost) {
          throw new Error(`Insufficient XP! You need ${target.cost - currentXp} more XP to purchase this item.`);
        }
        return {
          success: true,
          item: target.name,
          xp_spent: target.cost,
          remaining_xp: currentXp - target.cost,
        };
      }
    },
    onSuccess: (data, itemId) => {
      const target = catalogItems.find((i) => i.id === itemId);
      const updatedInv = [...localInventory, itemId];
      setLocalInventory(updatedInv);
      localStorage.setItem("purchased_shop_items", JSON.stringify(updatedInv));

      const newXp = currentXp - (target?.cost || 0);
      setAvailableXp(newXp);
      localStorage.setItem("user_custom_xp", newXp.toString());

      queryClient.invalidateQueries({ queryKey: ["shopItems"] });
      queryClient.invalidateQueries({ queryKey: ["myTotalXp"] });
      queryClient.invalidateQueries({ queryKey: ["contributorStats"] });

      toast.success(`🎉 Unlocked ${data.item || target?.name}! Added to your inventory vault.`);
      setConfirmItem(null);
    },
    onError: (err: Error) => {
      toast.error(err.message || "Failed to complete purchase.");
    },
    onSettled: () => setPurchasingId(null),
  });

  const handlePurchase = (item: ShopItemData) => {
    if (currentXp < item.cost) {
      toast.error(`Insufficient XP! You need ${item.cost - currentXp} more XP.`);
      return;
    }
    setConfirmItem(item);
  };

  const executePurchase = () => {
    if (!confirmItem) return;
    setPurchasingId(confirmItem.id);
    purchaseMutation.mutate(confirmItem.id);
  };

  const toggleEquipItem = (id: number) => {
    let next: number[];
    if (equippedItemIds.includes(id)) {
      next = equippedItemIds.filter((i) => i !== id);
      toast("Item unequipped.", { icon: "🎒" });
    } else {
      next = [...equippedItemIds, id];
      toast.success("Item equipped to your profile!");
    }
    setEquippedItemIds(next);
    localStorage.setItem("equipped_shop_items", JSON.stringify(next));
  };

  return (
    <div className="max-w-5xl mx-auto px-4 pt-28 pb-16 space-y-10 font-sans">
      {/* Back Link */}
      <div>
        <Link
          to="/dashboard"
          className="inline-flex items-center gap-2 rounded-full bg-white dark:bg-[#1f1c18] dark:text-[#f0ebe2] px-4 py-2 text-xs font-black border-2 border-black shadow-card-sm hover:bg-gray-100 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Dashboard
        </Link>
      </div>

      {/* Hero Banner */}
      <section className="rounded-[2.5rem] border-4 border-black bg-gradient-to-br from-amber-400 via-orange-500 to-pink-500 p-8 sm:p-10 text-white shadow-card relative overflow-hidden">
        <div className="absolute -right-10 -bottom-10 text-[12rem] opacity-10 select-none pointer-events-none">
          🛍️
        </div>
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-3 max-w-xl">
            <span className="font-black text-xs bg-white/90 text-black px-4 py-2 rounded-full border-2 border-black inline-block shadow-card-sm">
              Atelier XP Marketplace 🛍️
            </span>
            <h1 className="text-3xl sm:text-5xl font-black text-white drop-shadow-[2px_2px_0_rgba(0,0,0,0.3)] tracking-tight">
              XP Rewards Store
            </h1>
            <p className="text-white/90 font-bold text-base sm:text-lg leading-relaxed">
              Earn XP by contributing to issues and completing learning challenges, then redeem your points for power-ups, badges, and cosmetics!
            </p>
          </div>

          {/* XP Balance Widget */}
          <div className="bg-white/95 text-black border-4 border-black rounded-[2rem] p-6 text-center shadow-card shrink-0 space-y-1 min-w-[200px]">
            <div className="flex items-center justify-center gap-2 text-amber-500 font-black text-3xl drop-shadow-[1px_1px_0_rgba(0,0,0,1)]">
              <Coins className="w-8 h-8 fill-amber-400 text-black stroke-[2.5]" />
              {currentXp}
            </div>
            <p className="text-xs font-black uppercase tracking-widest text-gray-600">
              Available XP
            </p>
          </div>
        </div>
      </section>

      {/* Store vs Vault Navigation Tabs */}
      <div className="flex items-center justify-between gap-4 border-b-4 border-black dark:border-[#2e2924] pb-4 flex-wrap">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setActiveTab("store")}
            className={`px-6 py-3 rounded-2xl border-4 border-black font-black text-sm transition-all shadow-card ${
              activeTab === "store"
                ? "bg-amber-300 text-black shadow-card-sm translate-y-0.5"
                : "bg-white text-black dark:bg-[#1f1c18] dark:text-[#f0ebe2] dark:border-[#2e2924] hover:bg-gray-100"
            }`}
          >
            <ShoppingBag className="w-4 h-4 inline mr-2" />
            Store Catalog
          </button>

          <button
            onClick={() => setActiveTab("vault")}
            className={`px-6 py-3 rounded-2xl border-4 border-black font-black text-sm transition-all shadow-card ${
              activeTab === "vault"
                ? "bg-amber-300 text-black shadow-card-sm translate-y-0.5"
                : "bg-white text-black dark:bg-[#1f1c18] dark:text-[#f0ebe2] dark:border-[#2e2924] hover:bg-gray-100"
            }`}
          >
            <Package className="w-4 h-4 inline mr-2" />
            My Vault ({ownedItems.length})
          </button>
        </div>

        {/* Category Pills (Store Mode) */}
        {activeTab === "store" && (
          <div className="flex items-center gap-1.5 flex-wrap">
            {CATEGORIES.map((cat) => (
              <button
                key={cat.id}
                onClick={() => setSelectedCategory(cat.id)}
                className={`px-3 py-1.5 rounded-full border-2 border-black text-xs font-black transition-all shadow-card-sm ${
                  selectedCategory === cat.id
                    ? "bg-black text-white dark:bg-white dark:text-black"
                    : "bg-white text-black dark:bg-[#1f1c18] dark:text-[#c4bbae] dark:border-[#2e2924] hover:bg-gray-100"
                }`}
              >
                {cat.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Main Catalog View */}
      {activeTab === "store" && (
        <section className="space-y-6">
          {isLoading ? (
            <div
              className="grid grid-cols-1 md:grid-cols-2 gap-6"
              data-testid="shop-loading-skeleton"
            >
              {Array.from({ length: 4 }).map((_, i) => (
                <div
                  key={i}
                  className="rounded-[2rem] border-4 border-black bg-white dark:bg-[#1f1c18] dark:border-[#2e2924] p-6 shadow-card space-y-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-4">
                      <Skeleton className="w-16 h-16 rounded-2xl shrink-0" />
                      <div className="space-y-2">
                        <Skeleton className="h-4 w-20 rounded-full" />
                        <Skeleton className="h-6 w-40 rounded" />
                      </div>
                    </div>
                    <Skeleton className="h-8 w-20 rounded-full" />
                  </div>
                  <Skeleton className="h-4 w-full rounded" />
                  <Skeleton className="h-4 w-3/4 rounded" />
                  <div className="pt-2 flex items-center justify-between border-t-2 border-dashed border-gray-200 dark:border-[#2e2924]">
                    <Skeleton className="h-4 w-28 rounded" />
                    <Skeleton className="h-10 w-28 rounded-xl" />
                  </div>
                </div>
              ))}
            </div>
          ) : filteredItems.length === 0 ? (
            <div className="rounded-[2rem] border-4 border-black bg-white dark:bg-[#1f1c18] dark:border-[#2e2924] p-12 text-center shadow-card space-y-3">
              <Gift className="w-12 h-12 mx-auto text-gray-400" />
              <h3 className="text-xl font-black dark:text-[#f0ebe2]">No items found</h3>
              <p className="text-xs font-bold text-gray-500">Try switching categories or check back later!</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {filteredItems.map((item) => {
                const isOwned = item.already_purchased;
                const canAfford = currentXp >= item.cost;
                const rarityStyle = RARITY_BADGE_STYLES[item.rarity || "RARE"];

                return (
                  <div
                    key={item.id}
                    className="rounded-[2rem] border-4 border-black bg-white dark:bg-[#1f1c18] dark:border-[#2e2924] p-6 shadow-card hover:-translate-y-1 transition-transform flex flex-col justify-between space-y-4 relative overflow-hidden"
                  >
                    <div className="space-y-3">
                      {/* Header Row */}
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-center gap-4">
                          <div className="bg-amber-100 dark:bg-amber-900/30 border-2 border-black p-3.5 rounded-2xl text-4xl shadow-card-sm flex items-center justify-center shrink-0">
                            {item.icon_emoji}
                          </div>
                          <div>
                            <span className={`text-[10px] font-black uppercase px-2.5 py-0.5 rounded-full border shadow-card-sm ${rarityStyle}`}>
                              {item.rarity || "RARE"}
                            </span>
                            <h3 className="text-lg font-black dark:text-[#f0ebe2] mt-1">
                              {item.name}
                            </h3>
                          </div>
                        </div>

                        <div className="bg-amber-300 text-black border-2 border-black px-3.5 py-1.5 rounded-full font-black text-sm flex items-center gap-1.5 shadow-card-sm shrink-0">
                          <Coins className="w-4 h-4 fill-amber-500 stroke-[2]" />
                          {item.cost}
                        </div>
                      </div>

                      <p className="text-xs font-bold text-gray-600 dark:text-[#c4bbae] leading-relaxed">
                        {item.description}
                      </p>

                      {item.benefit && (
                        <div className="inline-flex items-center gap-1.5 px-3 py-1 bg-indigo-50 dark:bg-indigo-950/40 text-indigo-900 dark:text-indigo-200 border-2 border-black rounded-xl text-xs font-extrabold shadow-card-sm">
                          <Sparkles className="w-3.5 h-3.5 text-amber-500 shrink-0" /> {item.benefit}
                        </div>
                      )}
                    </div>

                    {/* Action Button */}
                    <div className="pt-2">
                      {isOwned ? (
                        <div className="w-full py-3 bg-green-400 text-black font-black text-xs rounded-2xl border-2 border-black shadow-card-sm flex items-center justify-center gap-2">
                          <CheckCircle2 className="w-4 h-4 text-black" />
                          Unlocked & Owned
                        </div>
                      ) : (
                        <button
                          onClick={() => handlePurchase(item)}
                          disabled={!canAfford}
                          className={`w-full py-3 px-5 font-black text-xs rounded-2xl border-2 border-black transition-colors flex items-center justify-center gap-2 shadow-card-sm ${
                            canAfford
                              ? "bg-black text-white dark:bg-white dark:text-black hover:bg-gray-800 dark:hover:bg-gray-200"
                              : "bg-gray-200 text-gray-500 border-gray-400 cursor-not-allowed"
                          } ${CARD_FOCUS_RING}`}
                        >
                          <ShoppingBag className="w-4 h-4" />
                          {canAfford ? "Buy Item" : `Need ${item.cost - currentXp} More XP`}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      )}

      {/* Vault Inventory View */}
      {activeTab === "vault" && (
        <section className="space-y-6">
          {ownedItems.length === 0 ? (
            <div className="rounded-[2rem] border-4 border-black bg-white dark:bg-[#1f1c18] dark:border-[#2e2924] p-12 text-center shadow-card space-y-3">
              <Package className="w-12 h-12 mx-auto text-gray-400" />
              <h3 className="text-xl font-black dark:text-[#f0ebe2]">Your Vault is empty</h3>
              <p className="text-xs font-bold text-gray-500">Purchase items from the store to add them to your inventory!</p>
              <button
                onClick={() => setActiveTab("store")}
                className="mt-3 inline-flex items-center gap-2 px-5 py-2.5 bg-black text-white dark:bg-white dark:text-black font-black text-xs rounded-full border-2 border-black shadow-card-sm"
              >
                Browse Store Catalog
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {ownedItems.map((item) => {
                const isEquipped = equippedItemIds.includes(item.id);

                return (
                  <div
                    key={item.id}
                    className="rounded-[2rem] border-4 border-black bg-white dark:bg-[#1f1c18] dark:border-[#2e2924] p-6 shadow-card flex flex-col justify-between space-y-4"
                  >
                    <div className="space-y-3">
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-3">
                          <div className="bg-amber-100 dark:bg-amber-900/30 border-2 border-black p-3.5 rounded-2xl text-3xl shadow-card-sm">
                            {item.icon_emoji}
                          </div>
                          <div>
                            <span className="text-[10px] font-black uppercase px-2.5 py-0.5 rounded-full bg-green-400 text-black border border-black shadow-card-sm">
                              Owned Item
                            </span>
                            <h3 className="text-lg font-black dark:text-[#f0ebe2] mt-1">
                              {item.name}
                            </h3>
                          </div>
                        </div>
                        {isEquipped && (
                          <span className="font-black text-xs bg-indigo-500 text-white px-3 py-1 rounded-full border-2 border-black shadow-card-sm">
                            Equipped
                          </span>
                        )}
                      </div>
                      <p className="text-xs font-bold text-gray-600 dark:text-[#c4bbae]">
                        {item.description}
                      </p>
                    </div>

                    <button
                      onClick={() => toggleEquipItem(item.id)}
                      className={`w-full py-2.5 px-4 font-black text-xs rounded-2xl border-2 border-black transition-colors shadow-card-sm flex items-center justify-center gap-2 ${
                        isEquipped
                          ? "bg-gray-200 text-black hover:bg-gray-300"
                          : "bg-amber-300 text-black hover:bg-amber-400"
                      }`}
                    >
                      {isEquipped ? <Check className="w-4 h-4" /> : <Sparkles className="w-4 h-4" />}
                      {isEquipped ? "Unequip Item" : "Equip to Profile"}
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      )}

      {/* Confirmation Modal */}
      {confirmItem && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="rounded-[2.5rem] border-4 border-black bg-white dark:bg-[#1f1c18] dark:border-[#2e2924] p-8 shadow-card max-w-md w-full space-y-6 animate-fadeIn">
            <div className="text-center space-y-3">
              <div className="w-20 h-20 bg-amber-100 dark:bg-amber-900/30 border-4 border-black rounded-3xl mx-auto flex items-center justify-center text-5xl shadow-card">
                {confirmItem.icon_emoji}
              </div>
              <h3 className="text-2xl font-black dark:text-[#f0ebe2]">
                Unlock {confirmItem.name}?
              </h3>
              <p className="text-xs font-bold text-gray-600 dark:text-[#c4bbae]">
                This will deduct <span className="font-black text-amber-600 dark:text-amber-400">{confirmItem.cost} XP</span> from your balance.
              </p>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => setConfirmItem(null)}
                className="flex-1 py-3 px-4 bg-gray-100 dark:bg-[#25211c] text-black dark:text-[#f0ebe2] font-black text-xs rounded-2xl border-2 border-black hover:bg-gray-200 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={executePurchase}
                disabled={purchaseMutation.isPending}
                className="flex-1 py-3 px-4 bg-amber-400 hover:bg-amber-300 text-black font-black text-xs rounded-2xl border-2 border-black transition-colors flex items-center justify-center gap-2 shadow-card-sm disabled:opacity-50"
              >
                {purchaseMutation.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Sparkles className="w-4 h-4 fill-black" />
                )}
                Confirm Unlock
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ShopPage;
