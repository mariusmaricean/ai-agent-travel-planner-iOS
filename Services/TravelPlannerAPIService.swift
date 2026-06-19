import Foundation

enum TravelPlannerAPIError: LocalizedError, Sendable {
    case invalidResponse
    case serverError(Int)
    case emptyBaseURL

    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            "The travel planner server returned an invalid response."
        case let .serverError(statusCode):
            "The travel planner server returned status \(statusCode)."
        case .emptyBaseURL:
            "Set TRAVEL_PLANNER_API_BASE_URL before using the live travel planner service."
        }
    }
}

struct TravelPlannerAPIService: TravelPlanningServicing, Sendable {
    private let baseURL: URL
    private let session: URLSession

    init(
        baseURL: URL,
        session: URLSession = .shared
    ) {
        self.baseURL = baseURL
        self.session = session
    }

    func makePlan(for brief: TripBrief) async throws -> TripPlanResult {
        let request = try makeRequest(for: brief)
        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw TravelPlannerAPIError.invalidResponse
        }

        guard (200...299).contains(httpResponse.statusCode) else {
            throw TravelPlannerAPIError.serverError(httpResponse.statusCode)
        }

        return try JSONDecoder().decode(TripPlanResponse.self, from: data).result()
    }

    private func makeRequest(for brief: TripBrief) throws -> URLRequest {
        let endpoint = baseURL.appending(path: "trip-plans")
        let dateFormatter = ISO8601DateFormatter()
        dateFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]

        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.httpBody = try JSONEncoder().encode(TripPlanRequest(brief: brief, dateFormatter: dateFormatter))
        return request
    }
}
