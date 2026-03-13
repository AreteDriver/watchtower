/// WatchTower Subscription — on-chain tier access via SUI or LUX payment.
///
/// Players pay SUI (or transfer LUX items) to subscribe.
/// Emits SubscriptionPurchased events that the poller indexes
/// to grant backend tier access.
///
/// Tier pricing (in MIST — 1 SUI = 1_000_000_000 MIST):
///   Scout (1):     0.5 SUI / 7 days
///   Oracle (2):    2.0 SUI / 7 days
///   Spymaster (3): 5.0 SUI / 7 days
module watchtower::subscription {
    use sui::coin::{Self, Coin};
    use sui::event;
    use sui::sui::SUI;
    use sui::table::{Self, Table};

    // ===== Error codes =====
    const EInvalidTier: u64 = 1;
    const EInsufficientPayment: u64 = 2;
    const EInvalidDuration: u64 = 3;

    // ===== Tier constants =====
    const TIER_SCOUT: u8 = 1;
    const TIER_ORACLE: u8 = 2;
    const TIER_SPYMASTER: u8 = 3;

    // ===== Pricing (MIST per 7 days) =====
    const PRICE_SCOUT: u64 = 500_000_000;      // 0.5 SUI
    const PRICE_ORACLE: u64 = 2_000_000_000;    // 2.0 SUI
    const PRICE_SPYMASTER: u64 = 5_000_000_000; // 5.0 SUI

    // ===== Duration =====
    const DURATION_7_DAYS_MS: u64 = 604_800_000; // 7 days in ms

    // ===== Structs =====

    /// Admin capability — held by WatchTower deployer.
    public struct AdminCap has key, store {
        id: UID,
    }

    /// Shared subscription registry. Tracks active subs + collects revenue.
    public struct SubscriptionRegistry has key {
        id: UID,
        subscriptions: Table<address, SubscriptionRecord>,
        total_subscriptions: u64,
        total_revenue_mist: u64,
        treasury: address,
    }

    /// On-chain subscription record for a wallet.
    public struct SubscriptionRecord has store, copy, drop {
        tier: u8,
        expires_at_ms: u64,
        purchased_at_ms: u64,
        total_paid_mist: u64,
    }

    // ===== Events =====

    /// Emitted on every subscription purchase. Poller indexes this.
    public struct SubscriptionPurchased has copy, drop {
        subscriber: address,
        tier: u8,
        expires_at_ms: u64,
        paid_mist: u64,
    }

    /// Emitted when admin grants a comp subscription.
    public struct SubscriptionGranted has copy, drop {
        subscriber: address,
        tier: u8,
        expires_at_ms: u64,
        granted_by: address,
    }

    /// Emitted when admin credits a subscription after off-chain LUX payment verification.
    public struct LuxPaymentCredited has copy, drop {
        subscriber: address,
        tier: u8,
        expires_at_ms: u64,
    }

    // ===== Init =====

    fun init(ctx: &mut TxContext) {
        let sender = ctx.sender();

        transfer::transfer(
            AdminCap { id: object::new(ctx) },
            sender,
        );

        transfer::share_object(
            SubscriptionRegistry {
                id: object::new(ctx),
                subscriptions: table::new(ctx),
                total_subscriptions: 0,
                total_revenue_mist: 0,
                treasury: sender,
            },
        );
    }

    // ===== Public: Subscribe with SUI =====

    /// Purchase a subscription tier with SUI.
    /// Exact payment required. Extends if already subscribed.
    public fun subscribe(
        registry: &mut SubscriptionRegistry,
        tier: u8,
        mut payment: Coin<SUI>,
        clock: &sui::clock::Clock,
        ctx: &mut TxContext,
    ) {
        // Validate tier
        assert!(tier >= TIER_SCOUT && tier <= TIER_SPYMASTER, EInvalidTier);

        // Check payment amount
        let required = tier_price(tier);
        let paid = coin::value(&payment);
        assert!(paid >= required, EInsufficientPayment);

        // Send exact amount to treasury, refund overpayment
        let treasury_coin = coin::split(&mut payment, required, ctx);
        transfer::public_transfer(treasury_coin, registry.treasury);

        // Refund remainder if any
        if (coin::value(&payment) > 0) {
            transfer::public_transfer(payment, ctx.sender());
        } else {
            coin::destroy_zero(payment);
        };

        // Calculate expiry
        let now_ms = sui::clock::timestamp_ms(clock);
        let subscriber = ctx.sender();

        let expires_at_ms = if (registry.subscriptions.contains(subscriber)) {
            let existing = registry.subscriptions.borrow(subscriber);
            let base = if (existing.expires_at_ms > now_ms) {
                existing.expires_at_ms
            } else {
                now_ms
            };
            base + DURATION_7_DAYS_MS
        } else {
            now_ms + DURATION_7_DAYS_MS
        };

        // Upsert subscription
        let record = SubscriptionRecord {
            tier,
            expires_at_ms,
            purchased_at_ms: now_ms,
            total_paid_mist: required,
        };

        if (registry.subscriptions.contains(subscriber)) {
            let existing = registry.subscriptions.borrow_mut(subscriber);
            // Keep higher tier, extend expiry
            existing.tier = if (tier > existing.tier) { tier } else { existing.tier };
            existing.expires_at_ms = expires_at_ms;
            existing.purchased_at_ms = now_ms;
            existing.total_paid_mist = existing.total_paid_mist + required;
        } else {
            registry.subscriptions.add(subscriber, record);
            registry.total_subscriptions = registry.total_subscriptions + 1;
        };

        registry.total_revenue_mist = registry.total_revenue_mist + required;

        // Emit event for poller
        event::emit(SubscriptionPurchased {
            subscriber,
            tier,
            expires_at_ms,
            paid_mist: required,
        });
    }

    // ===== Admin: Grant comp subscription =====

    /// Grant a free subscription (hackathon prizes, partnerships, etc).
    public fun grant_subscription(
        _cap: &AdminCap,
        registry: &mut SubscriptionRegistry,
        subscriber: address,
        tier: u8,
        duration_days: u64,
        clock: &sui::clock::Clock,
        ctx: &TxContext,
    ) {
        assert!(tier >= TIER_SCOUT && tier <= TIER_SPYMASTER, EInvalidTier);
        assert!(duration_days > 0 && duration_days <= 365, EInvalidDuration);

        let now_ms = sui::clock::timestamp_ms(clock);
        let duration_ms = duration_days * 86_400_000;

        let expires_at_ms = if (registry.subscriptions.contains(subscriber)) {
            let existing = registry.subscriptions.borrow(subscriber);
            let base = if (existing.expires_at_ms > now_ms) {
                existing.expires_at_ms
            } else {
                now_ms
            };
            base + duration_ms
        } else {
            now_ms + duration_ms
        };

        let record = SubscriptionRecord {
            tier,
            expires_at_ms,
            purchased_at_ms: now_ms,
            total_paid_mist: 0,
        };

        if (registry.subscriptions.contains(subscriber)) {
            let existing = registry.subscriptions.borrow_mut(subscriber);
            existing.tier = if (tier > existing.tier) { tier } else { existing.tier };
            existing.expires_at_ms = expires_at_ms;
            existing.purchased_at_ms = now_ms;
        } else {
            registry.subscriptions.add(subscriber, record);
            registry.total_subscriptions = registry.total_subscriptions + 1;
        };

        event::emit(SubscriptionGranted {
            subscriber,
            tier,
            expires_at_ms,
            granted_by: ctx.sender(),
        });
    }

    // ===== Admin: Credit LUX payment =====

    /// Admin credits a subscription after verifying LUX payment off-chain.
    /// Used for LUX token payments where the token contract isn't known at build time.
    public fun credit_lux_payment(
        _cap: &AdminCap,
        registry: &mut SubscriptionRegistry,
        subscriber: address,
        tier: u8,
        clock: &sui::clock::Clock,
        _ctx: &TxContext,
    ) {
        assert!(tier >= TIER_SCOUT && tier <= TIER_SPYMASTER, EInvalidTier);

        let now_ms = sui::clock::timestamp_ms(clock);

        let expires_at_ms = if (registry.subscriptions.contains(subscriber)) {
            let existing = registry.subscriptions.borrow(subscriber);
            let base = if (existing.expires_at_ms > now_ms) {
                existing.expires_at_ms
            } else {
                now_ms
            };
            base + DURATION_7_DAYS_MS
        } else {
            now_ms + DURATION_7_DAYS_MS
        };

        if (registry.subscriptions.contains(subscriber)) {
            let existing = registry.subscriptions.borrow_mut(subscriber);
            existing.tier = if (tier > existing.tier) { tier } else { existing.tier };
            existing.expires_at_ms = expires_at_ms;
            existing.purchased_at_ms = now_ms;
        } else {
            let record = SubscriptionRecord {
                tier,
                expires_at_ms,
                purchased_at_ms: now_ms,
                total_paid_mist: 0,
            };
            registry.subscriptions.add(subscriber, record);
            registry.total_subscriptions = registry.total_subscriptions + 1;
        };

        event::emit(LuxPaymentCredited {
            subscriber,
            tier,
            expires_at_ms,
        });
    }

    // ===== Public reads =====

    /// Get subscription record for a wallet. Aborts if not found.
    public fun get_subscription(
        registry: &SubscriptionRegistry,
        subscriber: address,
    ): &SubscriptionRecord {
        assert!(registry.subscriptions.contains(subscriber), EInvalidTier);
        registry.subscriptions.borrow(subscriber)
    }

    /// Check if a wallet has an active subscription at or above a given tier.
    public fun has_tier(
        registry: &SubscriptionRegistry,
        subscriber: address,
        min_tier: u8,
        clock: &sui::clock::Clock,
    ): bool {
        if (!registry.subscriptions.contains(subscriber)) {
            return false
        };
        let record = registry.subscriptions.borrow(subscriber);
        let now_ms = sui::clock::timestamp_ms(clock);
        record.tier >= min_tier && record.expires_at_ms > now_ms
    }

    /// Get tier price in MIST.
    public fun tier_price(tier: u8): u64 {
        if (tier == TIER_SCOUT) { PRICE_SCOUT }
        else if (tier == TIER_ORACLE) { PRICE_ORACLE }
        else if (tier == TIER_SPYMASTER) { PRICE_SPYMASTER }
        else { abort EInvalidTier }
    }

    /// Accessors
    public fun tier(record: &SubscriptionRecord): u8 { record.tier }
    public fun expires_at_ms(record: &SubscriptionRecord): u64 { record.expires_at_ms }
    public fun total_paid_mist(record: &SubscriptionRecord): u64 { record.total_paid_mist }
    public fun total_subscriptions(registry: &SubscriptionRegistry): u64 { registry.total_subscriptions }
    public fun total_revenue_mist(registry: &SubscriptionRegistry): u64 { registry.total_revenue_mist }

    // ===== Admin: Update treasury =====

    public fun update_treasury(
        _cap: &AdminCap,
        registry: &mut SubscriptionRegistry,
        new_treasury: address,
    ) {
        registry.treasury = new_treasury;
    }

    // ===== Test-only =====

    #[test_only]
    public fun init_for_testing(ctx: &mut TxContext) {
        init(ctx);
    }
}
