import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchApi } from "../lib/api";
import {
  Coins,
  Gift,
  Loader2,
  CheckCircle2,
  Sparkles,
  ShoppingBag,
  Lock,
  ArrowLeft,
} from "lucide-react";
import { Link } from "react-router-dom";

interface ShopItemData {
  id: number;
  name: string;
  description: string;
  item_type: string;
  cost: number;
  icon_emoji: string;
  is_limited: boolean;
  already_purchased: boolean;
}

interface PurchaseResponse {
  success: boolean;
  item: string;
  xp_spent: number;
  remaining_xp: number;
}

const ITEM_TYPE_LABELS: Record<string, string> = {
  streak_freeze: "Streak",
  profile_theme: "Theme",
  badge_unlock: "Badge",
  xp_boost: "Boost",
  custom_title: "Title",
};

function ShopItemCard({
  item,
  onPurchase,
  purchasing,
}: {
  item: ShopItemData;
  onPurchase: (id: number) => void;
  purchasing: boolean;
}) {
  const [showConfirm, setShowConfirm] = useState(false);

  if (item.already_purchased) {
    return (
      <div className="rounded-2xl border-4 border-green-500/30 bg-green-50/50 p-5 opacity-70 dark:bg-green-900/10">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="text-3xl">{item.icon_emoji}</span>
            <div>
              <h3 className="font-bold text-sm text-text dark:text-[#f0ebe2]">
                {item.name}
              </h3>
              <span className="text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
                Owned
              </span>
            </div>
          </div>
          <CheckCircle2 className="w-5 h-5 text-green-500 shrink-0" />
        </div>
        <p className="text-xs text-muted mt-2 ml-12">{item.description}</p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border-4 border-black/10 bg-white p-5 dark:border-[#2e2924] dark:bg-[#1f1c18]">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="text-3xl">{item.icon_emoji}</span>
          <div>
            <h3 className="font-bold text-sm text-text dark:text-[#f0ebe2]">
              {item.name}
            </h3>
            <span className="text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-accent/10 text-accent">
              {ITEM_TYPE_LABELS[item.item_type] || item.item_type}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-1 text-amber-600 font-bold text-sm shrink-0">
          <Coins className="w-3.5 h-3.5" />
          {item.cost}
        </div>
      </div>
      <p className="text-xs text-muted mt-2 ml-12">{item.description}</p>
      {item.is_limited && (
        <p className="text-[10px] text-muted mt-1 ml-12 flex items-center gap-1">
          <Lock className="w-3 h-3" />
          One per user
        </p>
      )}

      {!showConfirm ? (
        <button
          onClick={() => setShowConfirm(true)}
          className="mt-3 ml-12 w-[calc(100%-48px)] py-2 px-4 bg-accent hover:bg-accent/90 text-white font-bold text-xs rounded-xl border-2 border-black transition-colors"
        >
          <ShoppingBag className="w-3.5 h-3.5 inline mr-1.5" />
          Buy Now
        </button>
      ) : (
        <div className="mt-3 ml-12 w-[calc(100%-48px)] flex gap-2">
          <button
            onClick={() => setShowConfirm(false)}
            className="flex-1 py-2 px-3 bg-white text-text font-bold text-xs rounded-xl border-2 border-black/20 hover:bg-black/5 transition-colors dark:bg-[#151411] dark:border-[#2e2924]"
          >
            Cancel
          </button>
          <button
            onClick={() => {
              onPurchase(item.id);
              setShowConfirm(false);
            }}
            disabled={purchasing}
            className="flex-1 py-2 px-3 bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-white font-bold text-xs rounded-xl border-2 border-black transition-colors flex items-center justify-center gap-1"
          >
            {purchasing ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Sparkles className="w-3.5 h-3.5" />
            )}
            Confirm
          </button>
        </div>
      )}
    </div>
  );
}

export function ShopPage() {
  const queryClient = useQueryClient();
  const [purchasingId, setPurchasingId] = useState<number | null>(null);
  const [purchaseError, setPurchaseError] = useState<string | null>(null);

  const { data: items, isLoading } = useQuery({
    queryKey: ["shopItems"],
    queryFn: () =>
      fetchApi<ShopItemData[]>("/gamification/shop/", {
        suppressErrorToast: true,
      }),
  });

  const { data: totalXp } = useQuery({
    queryKey: ["myTotalXp"],
    queryFn: async () => {
      const data = await fetchApi<{ total_xp: number }>(
        "/gamification/my-xp/",
        { suppressErrorToast: true },
      );
      return data.total_xp;
    },
  });

  const purchaseMutation = useMutation({
    mutationFn: (itemId: number) =>
      fetchApi<PurchaseResponse>("/gamification/shop/purchase/", {
        method: "POST",
        body: JSON.stringify({ item_id: itemId }),
        headers: { "Content-Type": "application/json" },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["shopItems"] });
      queryClient.invalidateQueries({ queryKey: ["myTotalXp"] });
      queryClient.invalidateQueries({ queryKey: ["contributorStats"] });
      setPurchaseError(null);
    },
    onError: (err: Error) => {
      setPurchaseError(err.message);
    },
    onSettled: () => setPurchasingId(null),
  });

  const handlePurchase = (itemId: number) => {
    setPurchasingId(itemId);
    purchaseMutation.mutate(itemId);
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="mb-6">
        <Link
          to="/dashboard"
          className="inline-flex items-center gap-1.5 text-xs font-bold text-muted hover:text-text transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to Dashboard
        </Link>
      </div>

      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-black flex items-center gap-3 text-text dark:text-[#f0ebe2]">
            <ShoppingBag className="w-8 h-8 text-accent" />
            XP Shop
          </h1>
          <p className="text-sm text-muted mt-1">
            Spend your hard-earned XP on rewards and cosmetics
          </p>
        </div>
        <div className="bg-amber-50 border-2 border-amber-200 rounded-2xl px-5 py-3 text-center dark:bg-amber-900/20 dark:border-amber-700/30">
          <div className="flex items-center gap-1.5 text-amber-600 font-bold text-lg">
            <Coins className="w-5 h-5" />
            {totalXp ?? "—"}
          </div>
          <div className="text-[9px] font-mono uppercase tracking-wider text-muted">
            Available XP
          </div>
        </div>
      </div>

      {purchaseError && (
        <div className="mb-6 p-4 bg-red-50 border-2 border-red-200 rounded-2xl text-red-700 text-sm font-bold dark:bg-red-900/20 dark:border-red-800 dark:text-red-400">
          {purchaseError}
        </div>
      )}

      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-muted" />
        </div>
      ) : !items || items.length === 0 ? (
        <div className="text-center py-20 text-muted">
          <Gift className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p className="text-lg font-bold">Shop is empty</p>
          <p className="text-sm">Check back later for new items!</p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {items.map((item) => (
            <ShopItemCard
              key={item.id}
              item={item}
              onPurchase={handlePurchase}
              purchasing={purchasingId === item.id}
            />
          ))}
        </div>
      )}
    </div>
  );
}
