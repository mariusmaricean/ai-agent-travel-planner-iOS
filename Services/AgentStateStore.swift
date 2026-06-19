import Foundation

protocol AgentStateStoring {
    func load() -> PersistedAgentState?
    func save(_ state: PersistedAgentState)
    func clear()
}

struct UserDefaultsAgentStateStore: AgentStateStoring {
    private let storageKey = "travel-planner-ios-state-v1"
    private let defaults: UserDefaults

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    func load() -> PersistedAgentState? {
        guard let data = defaults.data(forKey: storageKey) else { return nil }
        return try? JSONDecoder().decode(PersistedAgentState.self, from: data)
    }

    func save(_ state: PersistedAgentState) {
        guard let data = try? JSONEncoder().encode(state) else { return }
        defaults.set(data, forKey: storageKey)
    }

    func clear() {
        defaults.removeObject(forKey: storageKey)
    }
}
