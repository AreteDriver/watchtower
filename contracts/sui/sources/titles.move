/// WatchTower Earned Titles
/// On-chain registry of deterministic titles earned from chain behavior.
/// "The Reaper", "The Ghost", "The Meatgrinder" — computed from data, stored forever.
module watchtower::titles {
    use sui::event;
    use sui::table::{Self, Table};
    use std::string::String;

    // ===== Structs =====

    /// Admin capability — same deployer as reputation module.
    public struct TitleOracleCap has key, store {
        id: UID,
    }

    /// Shared registry of all earned titles.
    public struct TitleRegistry has key {
        id: UID,
        /// entity_address → list of earned title strings
        titles: Table<address, vector<String>>,
        /// Total titles inscribed across all entities
        total_titles: u64,
        /// Total unique entities with at least one title
        total_titled: u64,
    }

    // ===== Events =====

    public struct TitleEarned has copy, drop {
        entity: address,
        title: String,
    }

    // ===== Init =====

    fun init(ctx: &mut TxContext) {
        transfer::transfer(
            TitleOracleCap { id: object::new(ctx) },
            ctx.sender(),
        );

        transfer::share_object(
            TitleRegistry {
                id: object::new(ctx),
                titles: table::new(ctx),
                total_titles: 0,
                total_titled: 0,
            },
        );
    }

    // ===== Oracle writes =====

    /// Grant a single earned title to an entity.
    /// Skips silently if entity already has this exact title.
    public fun grant_title(
        _cap: &TitleOracleCap,
        registry: &mut TitleRegistry,
        entity: address,
        title: String,
    ) {
        if (!registry.titles.contains(entity)) {
            registry.titles.add(entity, vector[title]);
            registry.total_titled = registry.total_titled + 1;
            registry.total_titles = registry.total_titles + 1;
            event::emit(TitleEarned { entity, title });
            return
        };

        let titles = registry.titles.borrow_mut(entity);
        // Check for duplicates
        let mut i = 0;
        let len = titles.length();
        while (i < len) {
            if (&titles[i] == &title) {
                return // Already has this title
            };
            i = i + 1;
        };

        titles.push_back(title);
        registry.total_titles = registry.total_titles + 1;
        event::emit(TitleEarned { entity, title });
    }

    /// Grant multiple titles to one entity in a single transaction.
    public fun grant_titles_batch(
        cap: &TitleOracleCap,
        registry: &mut TitleRegistry,
        entity: address,
        new_titles: vector<String>,
    ) {
        let mut i = 0;
        let len = new_titles.length();
        while (i < len) {
            grant_title(cap, registry, entity, new_titles[i]);
            i = i + 1;
        };
    }

    // ===== Public reads =====

    /// Get all titles for an entity. Returns empty vector if none.
    public fun get_titles(registry: &TitleRegistry, entity: address): vector<String> {
        if (!registry.titles.contains(entity)) {
            return vector[]
        };
        *registry.titles.borrow(entity)
    }

    /// Check if an entity has a specific title.
    public fun has_title(registry: &TitleRegistry, entity: address, title: &String): bool {
        if (!registry.titles.contains(entity)) {
            return false
        };
        let titles = registry.titles.borrow(entity);
        let mut i = 0;
        let len = titles.length();
        while (i < len) {
            if (&titles[i] == title) {
                return true
            };
            i = i + 1;
        };
        false
    }

    /// Number of titles an entity holds.
    public fun title_count(registry: &TitleRegistry, entity: address): u64 {
        if (!registry.titles.contains(entity)) {
            return 0
        };
        registry.titles.borrow(entity).length()
    }

    /// Total titles across all entities.
    public fun total_titles(registry: &TitleRegistry): u64 {
        registry.total_titles
    }

    /// Total unique entities with at least one title.
    public fun total_titled(registry: &TitleRegistry): u64 {
        registry.total_titled
    }

    // ===== Test-only =====

    #[test_only]
    public fun init_for_testing(ctx: &mut TxContext) {
        init(ctx);
    }
}
