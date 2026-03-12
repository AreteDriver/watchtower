/// WatchTower Reputation Oracle
/// Publishes entity reputation scores on-chain for Smart Assembly gating.
/// Any dapp or mod can query: "should I trust this pilot?"
module watchtower::reputation {
    use sui::event;
    use sui::table::{Self, Table};

    // ===== Error codes =====
    const EInvalidScore: u64 = 1;
    const EEntityNotFound: u64 = 2;

    // ===== Rating thresholds =====
    const RATING_TRUSTED: u8 = 80;
    const RATING_REPUTABLE: u8 = 60;
    const RATING_NEUTRAL: u8 = 40;
    const RATING_SUSPICIOUS: u8 = 20;

    // ===== Structs =====

    /// Admin capability — held by WatchTower deployer.
    /// Only the oracle can publish scores.
    public struct OracleCap has key, store {
        id: UID,
    }

    /// The shared registry of all reputation scores.
    public struct ReputationRegistry has key {
        id: UID,
        scores: Table<address, ReputationScore>,
        total_scored: u64,
        oracle: address,
    }

    /// On-chain reputation for a single entity.
    /// 6 dimensions (0-100 each) + weighted aggregate.
    public struct ReputationScore has store, copy, drop {
        /// Weighted aggregate trust score (0-100)
        trust_score: u8,
        /// Fair fighter vs serial ganker (weight: 25%)
        combat_honor: u8,
        /// Variety of opponents (weight: 15%)
        target_diversity: u8,
        /// Mutual fights / vendettas (weight: 20%)
        reciprocity: u8,
        /// Stable activity over time (weight: 15%)
        consistency: u8,
        /// Group participation (weight: 15%)
        community: u8,
        /// Not excessively lethal (weight: 10%)
        restraint: u8,
        /// Timestamp of last score computation (unix epoch)
        last_updated: u64,
    }

    // ===== Events =====

    public struct ScorePublished has copy, drop {
        entity: address,
        trust_score: u8,
        last_updated: u64,
    }

    public struct ScoreBatchPublished has copy, drop {
        count: u64,
        last_updated: u64,
    }

    // ===== Init =====

    /// Called once at package publish. Creates the oracle cap and shared registry.
    fun init(ctx: &mut TxContext) {
        let sender = ctx.sender();

        transfer::transfer(
            OracleCap { id: object::new(ctx) },
            sender,
        );

        transfer::share_object(
            ReputationRegistry {
                id: object::new(ctx),
                scores: table::new(ctx),
                total_scored: 0,
                oracle: sender,
            },
        );
    }

    // ===== Oracle writes =====

    /// Publish or update a single entity's reputation score.
    public fun publish_score(
        _cap: &OracleCap,
        registry: &mut ReputationRegistry,
        entity: address,
        trust_score: u8,
        combat_honor: u8,
        target_diversity: u8,
        reciprocity: u8,
        consistency: u8,
        community: u8,
        restraint: u8,
        timestamp: u64,
    ) {
        assert!(trust_score <= 100, EInvalidScore);
        assert!(combat_honor <= 100, EInvalidScore);
        assert!(target_diversity <= 100, EInvalidScore);
        assert!(reciprocity <= 100, EInvalidScore);
        assert!(consistency <= 100, EInvalidScore);
        assert!(community <= 100, EInvalidScore);
        assert!(restraint <= 100, EInvalidScore);

        let score = ReputationScore {
            trust_score,
            combat_honor,
            target_diversity,
            reciprocity,
            consistency,
            community,
            restraint,
            last_updated: timestamp,
        };

        if (registry.scores.contains(entity)) {
            *registry.scores.borrow_mut(entity) = score;
        } else {
            registry.scores.add(entity, score);
            registry.total_scored = registry.total_scored + 1;
        };

        event::emit(ScorePublished {
            entity,
            trust_score,
            last_updated: timestamp,
        });
    }

    /// Batch publish scores for multiple entities in one transaction.
    public fun publish_scores_batch(
        cap: &OracleCap,
        registry: &mut ReputationRegistry,
        entities: vector<address>,
        trust_scores: vector<u8>,
        combat_honors: vector<u8>,
        target_diversities: vector<u8>,
        reciprocities: vector<u8>,
        consistencies: vector<u8>,
        communities: vector<u8>,
        restraints: vector<u8>,
        timestamp: u64,
    ) {
        let len = entities.length();
        assert!(trust_scores.length() == len, EInvalidScore);
        assert!(combat_honors.length() == len, EInvalidScore);
        assert!(target_diversities.length() == len, EInvalidScore);
        assert!(reciprocities.length() == len, EInvalidScore);
        assert!(consistencies.length() == len, EInvalidScore);
        assert!(communities.length() == len, EInvalidScore);
        assert!(restraints.length() == len, EInvalidScore);

        let mut i = 0;
        while (i < len) {
            publish_score(
                cap,
                registry,
                entities[i],
                trust_scores[i],
                combat_honors[i],
                target_diversities[i],
                reciprocities[i],
                consistencies[i],
                communities[i],
                restraints[i],
                timestamp,
            );
            i = i + 1;
        };

        event::emit(ScoreBatchPublished {
            count: len,
            last_updated: timestamp,
        });
    }

    // ===== Public reads (for Smart Assemblies / other mods) =====

    /// Get the full reputation score for an entity.
    public fun get_score(registry: &ReputationRegistry, entity: address): &ReputationScore {
        assert!(registry.scores.contains(entity), EEntityNotFound);
        registry.scores.borrow(entity)
    }

    /// Quick trust check: is this entity at or above the given threshold?
    /// Usage: `is_trusted(registry, pilot_addr, 40)` → true if trust >= 40
    public fun is_trusted(registry: &ReputationRegistry, entity: address, min_trust: u8): bool {
        if (!registry.scores.contains(entity)) {
            return false
        };
        registry.scores.borrow(entity).trust_score >= min_trust
    }

    /// Get just the trust score (0-100). Returns 0 if entity not found.
    public fun trust_score(registry: &ReputationRegistry, entity: address): u8 {
        if (!registry.scores.contains(entity)) {
            return 0
        };
        registry.scores.borrow(entity).trust_score
    }

    /// Get the text rating category for an entity.
    /// 0 = unknown, 1 = dangerous, 2 = suspicious, 3 = neutral, 4 = reputable, 5 = trusted
    public fun rating(registry: &ReputationRegistry, entity: address): u8 {
        let score = trust_score(registry, entity);
        if (score >= RATING_TRUSTED) { 5 }
        else if (score >= RATING_REPUTABLE) { 4 }
        else if (score >= RATING_NEUTRAL) { 3 }
        else if (score >= RATING_SUSPICIOUS) { 2 }
        else if (score > 0) { 1 }
        else { 0 }
    }

    /// Total number of entities with published scores.
    public fun total_scored(registry: &ReputationRegistry): u64 {
        registry.total_scored
    }

    // ===== Score field accessors =====

    public fun combat_honor(score: &ReputationScore): u8 { score.combat_honor }
    public fun target_diversity(score: &ReputationScore): u8 { score.target_diversity }
    public fun reciprocity(score: &ReputationScore): u8 { score.reciprocity }
    public fun consistency(score: &ReputationScore): u8 { score.consistency }
    public fun community(score: &ReputationScore): u8 { score.community }
    public fun restraint(score: &ReputationScore): u8 { score.restraint }
    public fun last_updated(score: &ReputationScore): u64 { score.last_updated }

    // ===== Test-only =====

    #[test_only]
    public fun init_for_testing(ctx: &mut TxContext) {
        init(ctx);
    }
}
