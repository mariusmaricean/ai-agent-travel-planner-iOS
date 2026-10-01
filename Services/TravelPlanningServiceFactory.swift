import Foundation

enum TravelPlanningServiceFactory {
    static func makeService() -> TravelPlanningServicing {
        guard let baseURL = TravelPlannerAPIConfiguration.baseURL else {
            return MockTravelPlanningService()
        }

        return TravelPlannerAPIService(baseURL: baseURL)
    }
}

enum TravelPlannerAPIConfiguration {
    private static let baseURLKey = "TRAVEL_PLANNER_API_BASE_URL"

    static var baseURL: URL? {
        firstValidURL(
            Bundle.main.object(forInfoDictionaryKey: baseURLKey) as? String,
            ProcessInfo.processInfo.environment[baseURLKey]
        )
    }

    private static func firstValidURL(_ values: String?...) -> URL? {
        values
            .compactMap { $0?.trimmingCharacters(in: .whitespacesAndNewlines) }
            .first { !$0.isEmpty }
            .flatMap(URL.init(string:))
    }
}

enum TravelPlannerClientIdentity {
    private static let storageKey = "travel-planner-traveler-id-v1"
    private static let accountSessionKey = "travel-planner-account-session-v1"
    static let travelerID = loadOrCreateTravelerID()

    static func currentAccountSession() -> TravelPlannerAccountSession? {
        guard let data = UserDefaults.standard.data(forKey: accountSessionKey) else {
            return nil
        }

        return try? JSONDecoder().decode(TravelPlannerAccountSession.self, from: data)
    }

    static func saveAccountSession(_ session: TravelPlannerAccountSession) {
        guard let data = try? JSONEncoder().encode(session) else { return }
        UserDefaults.standard.set(data, forKey: accountSessionKey)
    }

    static func clearAccountSession() {
        UserDefaults.standard.removeObject(forKey: accountSessionKey)
    }

    private static func loadOrCreateTravelerID() -> String {
        if let savedID = UserDefaults.standard.string(forKey: storageKey), !savedID.isEmpty {
            return savedID
        }

        let newID = "ios-\(UUID().uuidString.lowercased())"
        UserDefaults.standard.set(newID, forKey: storageKey)
        return newID
    }
}
