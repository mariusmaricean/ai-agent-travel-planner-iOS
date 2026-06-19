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
